"""
Module bot_core.py - Classe Bot réutilisable pour le trading multi-paires.
Basé sur la stratégie 3 swings de spot_btcusd.py mais modulaire et thread-safe.
"""
import asyncio
import threading
from binance import AsyncClient, BinanceSocketManager
from binance.exceptions import BinanceAPIException, BinanceRequestException
from collections import deque
from time import strftime, localtime
from storage import insert_trade, update_position, clear_position, insert_log


class ThreeSwingsStrategy:
    """Stratégie 3 swings avec détection REALISTE (réutilisable)"""

    def __init__(self, left=3, right=3, max_candles=200, timeframe="1m", min_pivot_distance=20):
        self.left = left
        self.right = right
        self.max_candles = max_candles
        self.timeframe = timeframe
        self.min_pivot_distance = min_pivot_distance

        self.candles = deque(maxlen=max_candles)

        # Pivots confirmés (avec lag)
        self.low1 = None
        self.low2 = None
        self.low3 = None
        self.high1 = None
        self.high2 = None
        self.high3 = None

        self.low1_time = None
        self.high1_time = None

        # État structure
        self.current_structure = None
        self.last_signal = None
        self.signal_count = {"BUY": 0, "SELL": 0}
        self.false_signals = 0

        # Niveaux de breakout
        self.buy_level = None
        self.sell_level = None

    def add_candle(self, timestamp, open_price, high, low, close, volume):
        candle = {
            'timestamp': timestamp,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        }
        self.candles.append(candle)

    def detect_pivot_high(self, index):
        if index < self.left or index >= len(self.candles) - self.right:
            return None

        candles_list = list(self.candles)
        center_high = candles_list[index]['high']
        center_timestamp = candles_list[index]['timestamp']

        for i in range(index - self.left, index):
            if candles_list[i]['high'] >= center_high:
                return None

        for i in range(index + 1, index + self.right + 1):
            if candles_list[i]['high'] >= center_high:
                return None

        if self.high1 is not None:
            distance = abs(center_high - self.high1)
            if distance < self.min_pivot_distance:
                return None

        return (center_high, center_timestamp)

    def detect_pivot_low(self, index):
        if index < self.left or index >= len(self.candles) - self.right:
            return None

        candles_list = list(self.candles)
        center_low = candles_list[index]['low']
        center_timestamp = candles_list[index]['timestamp']

        for i in range(index - self.left, index):
            if candles_list[i]['low'] <= center_low:
                return None

        for i in range(index + 1, index + self.right + 1):
            if candles_list[i]['low'] <= center_low:
                return None

        if self.low1 is not None:
            distance = abs(center_low - self.low1)
            if distance < self.min_pivot_distance:
                return None

        return (center_low, center_timestamp)

    def update_pivots(self):
        """Détecte les pivots CONFIRMES (avec right bougies de lag)"""
        if len(self.candles) < self.left + self.right + 1:
            return

        check_index = len(self.candles) - self.right - 1

        pivot_low_data = self.detect_pivot_low(check_index)
        if pivot_low_data is not None:
            pivot_low, timestamp = pivot_low_data
            self.low3 = self.low2
            self.low2 = self.low1
            self.low1 = pivot_low
            self.low1_time = timestamp

        pivot_high_data = self.detect_pivot_high(check_index)
        if pivot_high_data is not None:
            pivot_high, timestamp = pivot_high_data
            self.high3 = self.high2
            self.high2 = self.high1
            self.high1 = pivot_high
            self.high1_time = timestamp

    def calculate_structure_strength(self):
        if not all([self.low1, self.low2, self.low3, self.high1, self.high2, self.high3]):
            return 0

        low_move_1 = abs(self.low1 - self.low2) / self.low2 * 100
        low_move_2 = abs(self.low2 - self.low3) / self.low3 * 100
        high_move_1 = abs(self.high1 - self.high2) / self.high2 * 100
        high_move_2 = abs(self.high2 - self.high3) / self.high3 * 100

        avg_strength = (low_move_1 + low_move_2 + high_move_1 + high_move_2) / 4
        return avg_strength

    def check_pivot_freshness(self):
        if not self.low1_time or not self.high1_time:
            return True

        current_time = list(self.candles)[-1]['timestamp']
        low_age = (current_time - self.low1_time) / 1000 / 60
        high_age = (current_time - self.high1_time) / 1000 / 60

        if low_age > 30 or high_age > 30:
            return False

        return True

    def analyze_structure(self, min_structure_strength=0.3):
        """Analyse structure (avec lag accepté)"""
        have_3_lows = all(x is not None for x in [self.low1, self.low2, self.low3])
        have_3_highs = all(x is not None for x in [self.high1, self.high2, self.high3])

        if not (have_3_lows and have_3_highs):
            return None

        strength = self.calculate_structure_strength()
        if strength < min_structure_strength:
            return None

        if not self.check_pivot_freshness():
            return None

        up_structure = (
            self.low1 > self.low2 > self.low3 and
            self.high1 > self.high2 > self.high3
        )

        down_structure = (
            self.low1 < self.low2 < self.low3 and
            self.high1 < self.high2 < self.high3
        )

        if up_structure:
            return "bullish"
        elif down_structure:
            return "bearish"
        else:
            return None

    def update_breakout_levels(self, breakout_threshold=0.05):
        """Définit les niveaux de breakout EN TEMPS REEL"""
        structure = self.analyze_structure()

        if structure == "bullish" and self.high1:
            self.buy_level = self.high1 * (1 + breakout_threshold / 100)
            self.sell_level = None

        elif structure == "bearish" and self.low1:
            self.sell_level = self.low1 * (1 - breakout_threshold / 100)
            self.buy_level = None

        else:
            self.buy_level = None
            self.sell_level = None

    def check_breakout(self, current_price, signal_cooldown=10, last_signal_time=0):
        """Vérifie si le prix actuel casse un niveau"""
        if len(self.candles) == 0:
            return None

        current_time = list(self.candles)[-1]['timestamp'] / 1000 / 60
        time_since_last = current_time - last_signal_time

        if time_since_last < signal_cooldown:
            return None

        # BUY si prix casse le niveau haut
        if self.buy_level and current_price > self.buy_level:
            self.last_signal = "BUY"
            self.signal_count["BUY"] += 1
            self.buy_level = None  # Reset niveau
            return ("BUY", current_time)

        # SELL si prix casse le niveau bas
        if self.sell_level and current_price < self.sell_level:
            self.last_signal = "SELL"
            self.signal_count["SELL"] += 1
            self.sell_level = None  # Reset niveau
            return ("SELL", current_time)

        return None

    def get_status(self):
        strength = self.calculate_structure_strength()
        fresh = self.check_pivot_freshness()

        return {
            'structure': self.current_structure,
            'strength': strength,
            'pivots_fresh': fresh,
            'last_signal': self.last_signal,
            'signal_count': self.signal_count,
            'pivots': {
                'highs': [self.high3, self.high2, self.high1],
                'lows': [self.low3, self.low2, self.low1]
            },
            'breakout_levels': {
                'buy': self.buy_level,
                'sell': self.sell_level
            },
            'candles_count': len(self.candles)
        }


class Bot:
    """
    Bot de trading modulaire utilisant la stratégie 3 swings.
    Peut être lancé dans un thread séparé et géré par le dashboard.
    """

    def __init__(self, symbol: str, interval: str = "1m",
                 risk_pct: float = 0.1, max_pos: float = 0.0,
                 testnet: bool = True, dry_run: bool = True,
                 api_key: str = "", api_secret: str = ""):
        self.symbol = symbol
        self.interval = interval
        self.risk_pct = risk_pct
        self.max_pos = max_pos
        self.testnet = testnet
        self.dry_run = dry_run
        self.api_key = api_key
        self.api_secret = api_secret

        # État de la position
        self.pos_side = "FLAT"  # FLAT | LONG
        self.pos_qty = 0.0
        self.entry_price = 0.0

        # Stratégie
        self.strategy = ThreeSwingsStrategy(
            left=3, right=3, timeframe=interval, min_pivot_distance=20
        )

        # État du bot
        self._is_running = False
        self._thread = None
        self._loop = None
        self.last_signal_time = 0

    def is_alive(self):
        """Vérifie si le bot est en cours d'exécution."""
        return self._is_running and self._thread and self._thread.is_alive()

    def start(self):
        """Démarre le bot dans un thread séparé."""
        if self.is_alive():
            insert_log(self.symbol, "WARNING", "Bot déjà en cours d'exécution")
            return

        self._is_running = True
        self._thread = threading.Thread(target=self._run_in_thread, daemon=True)
        self._thread.start()
        insert_log(self.symbol, "INFO", f"Bot démarré (testnet={self.testnet}, dry_run={self.dry_run})")

    def stop(self):
        """Arrête le bot."""
        self._is_running = False
        insert_log(self.symbol, "INFO", "Bot arrêté")

    def _run_in_thread(self):
        """Fonction exécutée dans le thread du bot."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._run_async())
        except Exception as e:
            insert_log(self.symbol, "ERROR", f"Erreur dans le bot: {e}")
        finally:
            self._loop.close()

    async def _run_async(self):
        """Logique asynchrone principale du bot."""
        client = None
        try:
            # Connexion à Binance
            client = await AsyncClient.create(self.api_key, self.api_secret, testnet=self.testnet)
            insert_log(self.symbol, "INFO", "Connecté à Binance")

            # Initialisation de la stratégie avec données historiques
            await self._initialize_strategy(client)

            # Écoute du websocket
            await self._listen_klines(client)

        except Exception as e:
            insert_log(self.symbol, "ERROR", f"Erreur: {e}")
        finally:
            if client:
                await client.close_connection()

    async def _initialize_strategy(self, client):
        """Initialise la stratégie avec les données historiques."""
        try:
            klines = await client.get_klines(symbol=self.symbol, interval=self.interval, limit=200)

            for kline in klines:
                self.strategy.add_candle(
                    kline[0],  # timestamp
                    float(kline[1]),  # open
                    float(kline[2]),  # high
                    float(kline[3]),  # low
                    float(kline[4]),  # close
                    float(kline[5])   # volume
                )

            # Scan des pivots initiaux
            for i in range(self.strategy.left, len(self.strategy.candles) - self.strategy.right):
                pivot_low_data = self.strategy.detect_pivot_low(i)
                if pivot_low_data is not None:
                    pivot_low, timestamp = pivot_low_data
                    self.strategy.low3 = self.strategy.low2
                    self.strategy.low2 = self.strategy.low1
                    self.strategy.low1 = pivot_low
                    self.strategy.low1_time = timestamp

                pivot_high_data = self.strategy.detect_pivot_high(i)
                if pivot_high_data is not None:
                    pivot_high, timestamp = pivot_high_data
                    self.strategy.high3 = self.strategy.high2
                    self.strategy.high2 = self.strategy.high1
                    self.strategy.high1 = pivot_high
                    self.strategy.high1_time = timestamp

            self.strategy.current_structure = self.strategy.analyze_structure()
            self.strategy.update_breakout_levels()

            status = self.strategy.get_status()
            insert_log(self.symbol, "INFO",
                      f"Stratégie initialisée: {status['structure'] or 'Non détectée'}, "
                      f"Force: {status['strength']:.2f}%")

        except Exception as e:
            insert_log(self.symbol, "ERROR", f"Erreur initialisation: {e}")

    async def _listen_klines(self, client):
        """Écoute les klines en temps réel via websocket."""
        bsm = BinanceSocketManager(client)
        ks = bsm.kline_socket(self.symbol, interval=self.interval)

        async with ks as kscm:
            while self._is_running:
                try:
                    msg = await asyncio.wait_for(kscm.recv(), timeout=60)

                    if not msg or 'k' not in msg:
                        continue

                    kline = msg['k']
                    current_close = float(kline['c'])

                    # Vérifier breakout sur chaque tick
                    signal_result = self.strategy.check_breakout(
                        current_close, signal_cooldown=10, last_signal_time=self.last_signal_time
                    )

                    if signal_result:
                        signal, current_time = signal_result
                        self.last_signal_time = current_time
                        await self._execute_signal(signal, current_close)

                    # Traiter bougie fermée
                    if kline['x']:  # Bougie fermée
                        timestamp = kline['t']
                        open_price = float(kline['o'])
                        high_price = float(kline['h'])
                        low_price = float(kline['l'])
                        close_price = float(kline['c'])
                        volume = float(kline['v'])

                        self.strategy.add_candle(timestamp, open_price, high_price, low_price, close_price, volume)
                        self.strategy.update_pivots()
                        self.strategy.current_structure = self.strategy.analyze_structure()
                        self.strategy.update_breakout_levels()

                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    insert_log(self.symbol, "ERROR", f"Erreur websocket: {e}")

    async def _execute_signal(self, signal: str, price: float):
        """Exécute un signal de trading."""
        try:
            insert_log(self.symbol, "INFO",
                      f"Signal {signal} reçu à {price:.2f} (dry_run={self.dry_run})")

            if signal == "BUY" and self.pos_side == "FLAT":
                # Calculer la quantité
                # Pour simplifier, on utilise risk_pct du capital disponible
                # En production, il faudrait récupérer le balance réel
                qty = self.risk_pct * 100 / price  # Exemple simplifié

                if not self.dry_run:
                    # Ici on placerait l'ordre réel via l'API
                    pass

                # Mise à jour position
                self.pos_side = "LONG"
                self.pos_qty = qty
                self.entry_price = price

                # Enregistrement
                insert_trade(self.symbol, "BUY", qty, price, qty * price)
                update_position(self.symbol, "LONG", qty, price, price, 0.0)

                insert_log(self.symbol, "INFO",
                          f"Position LONG ouverte: {qty:.8f} @ {price:.2f}")

            elif signal == "SELL" and self.pos_side == "LONG":
                # Calculer PnL
                pnl = (price - self.entry_price) * self.pos_qty

                if not self.dry_run:
                    # Ici on placerait l'ordre réel via l'API
                    pass

                # Enregistrement
                insert_trade(self.symbol, "SELL", self.pos_qty, price,
                           self.pos_qty * price, pnl, entry_price=self.entry_price)
                clear_position(self.symbol)

                insert_log(self.symbol, "INFO",
                          f"Position fermée: {self.pos_qty:.8f} @ {price:.2f}, PnL: {pnl:.2f}")

                # Reset position
                self.pos_side = "FLAT"
                self.pos_qty = 0.0
                self.entry_price = 0.0

        except Exception as e:
            insert_log(self.symbol, "ERROR", f"Erreur exécution signal: {e}")
