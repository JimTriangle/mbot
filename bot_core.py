"""
Module bot_core.py - Classe Bot réutilisable pour le trading multi-paires.
Supporte plusieurs stratégies de trading configurables.
"""
import asyncio
import threading
from binance import AsyncClient, BinanceSocketManager
from binance.exceptions import BinanceAPIException, BinanceRequestException
from collections import deque
from time import strftime, localtime
from typing import Dict, Any, Optional
from storage import insert_trade, update_position, clear_position, insert_log
from strategies import create_strategy, get_strategy_class


class TrendPhaseStrategy:
    """
    Stratégie de détection de phases de tendance basée sur EMA, RSI et ADX/DMI.
    Inspirée du Pine Script "Phases de Tendance (Optimisé+)".
    """

    def __init__(self,
                 ema_short_length=20,
                 ema_long_length=50,
                 rsi_length=14,
                 adx_length=14,
                 adx_smoothing=14,
                 adx_trend_threshold=25,
                 rsi_up_threshold=55,
                 rsi_down_threshold=35,
                 max_candles=200,
                 timeframe="1m"):

        # Paramètres
        self.ema_short_length = ema_short_length
        self.ema_long_length = ema_long_length
        self.rsi_length = rsi_length
        self.adx_length = adx_length
        self.adx_smoothing = adx_smoothing
        self.adx_trend_threshold = adx_trend_threshold
        self.rsi_up_threshold = rsi_up_threshold
        self.rsi_down_threshold = rsi_down_threshold
        self.max_candles = max_candles
        self.timeframe = timeframe

        # Données
        self.candles = deque(maxlen=max_candles)

        # États
        self.current_structure = None
        self.strong_up_trend = False
        self.strong_down_trend = False
        self.previous_strong_up_trend = False
        self.previous_strong_down_trend = False

        # Signaux
        self.last_signal = None
        self.signal_count = {"BUY": 0, "SELL": 0}

        # Indicateurs calculés
        self.ema_short = None
        self.ema_long = None
        self.rsi = None
        self.adx = None
        self.plus_di = None
        self.minus_di = None

    def add_candle(self, timestamp, open_price, high, low, close, volume):
        """Ajoute une bougie à l'historique"""
        candle = {
            'timestamp': timestamp,
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        }
        self.candles.append(candle)

    def update(self, candle):
        """
        Met à jour la stratégie avec une nouvelle bougie fermée.

        Args:
            candle: Dictionary avec les clés: timestamp, open, high, low, close, volume
        """
        self.add_candle(
            candle['timestamp'],
            candle['open'],
            candle['high'],
            candle['low'],
            candle['close'],
            candle['volume']
        )
        self._calculate_indicators()
        self._update_trend_state()

    def _calculate_ema(self, prices, period):
        """Calcule l'EMA (Exponential Moving Average)"""
        if len(prices) < period:
            return None

        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period

        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema

        return ema

    def _calculate_rsi(self, prices, period):
        """Calcule le RSI (Relative Strength Index)"""
        if len(prices) < period + 1:
            return None

        gains = []
        losses = []

        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        if len(gains) < period:
            return None

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _calculate_true_range(self, candles):
        """Calcule le True Range pour chaque bougie"""
        tr_values = []

        for i in range(1, len(candles)):
            high = candles[i]['high']
            low = candles[i]['low']
            prev_close = candles[i-1]['close']

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            tr_values.append(tr)

        return tr_values

    def _calculate_directional_movement(self, candles):
        """Calcule +DM et -DM (Directional Movement)"""
        plus_dm = []
        minus_dm = []

        for i in range(1, len(candles)):
            high_diff = candles[i]['high'] - candles[i-1]['high']
            low_diff = candles[i-1]['low'] - candles[i]['low']

            if high_diff > low_diff and high_diff > 0:
                plus_dm.append(high_diff)
                minus_dm.append(0)
            elif low_diff > high_diff and low_diff > 0:
                plus_dm.append(0)
                minus_dm.append(low_diff)
            else:
                plus_dm.append(0)
                minus_dm.append(0)

        return plus_dm, minus_dm

    def _smooth_values(self, values, period):
        """Lisse les valeurs (méthode Wilder's smoothing)"""
        if len(values) < period:
            return None

        smoothed = [sum(values[:period])]

        for i in range(period, len(values)):
            smoothed_value = (smoothed[-1] * (period - 1) + values[i]) / period
            smoothed.append(smoothed_value)

        return smoothed[-1] if smoothed else None

    def _calculate_dmi_adx(self, candles, adx_length, smoothing):
        """Calcule DMI (DI+, DI-) et ADX"""
        if len(candles) < adx_length + smoothing + 1:
            return None, None, None

        # Calcul True Range
        tr_values = self._calculate_true_range(candles)

        # Calcul Directional Movement
        plus_dm, minus_dm = self._calculate_directional_movement(candles)

        if len(tr_values) < adx_length or len(plus_dm) < adx_length:
            return None, None, None

        # Lissage des valeurs
        smoothed_tr = self._smooth_values(tr_values[-adx_length:], adx_length)
        smoothed_plus_dm = self._smooth_values(plus_dm[-adx_length:], adx_length)
        smoothed_minus_dm = self._smooth_values(minus_dm[-adx_length:], adx_length)

        if smoothed_tr is None or smoothed_tr == 0:
            return None, None, None

        # Calcul DI+ et DI-
        plus_di = (smoothed_plus_dm / smoothed_tr) * 100
        minus_di = (smoothed_minus_dm / smoothed_tr) * 100

        # Calcul DX et ADX (simplifié)
        di_sum = plus_di + minus_di
        if di_sum == 0:
            return plus_di, minus_di, None

        dx = abs(plus_di - minus_di) / di_sum * 100

        # ADX est une moyenne mobile du DX (simplifié ici)
        adx = dx  # Simplification: on pourrait faire une vraie EMA du DX

        return plus_di, minus_di, adx

    def _calculate_indicators(self):
        """Calcule tous les indicateurs techniques"""
        if len(self.candles) < max(self.ema_long_length, self.rsi_length, self.adx_length + self.adx_smoothing):
            return

        candles_list = list(self.candles)
        close_prices = [c['close'] for c in candles_list]

        # EMA
        self.ema_short = self._calculate_ema(close_prices, self.ema_short_length)
        self.ema_long = self._calculate_ema(close_prices, self.ema_long_length)

        # EMA précédente (pour détecter la croissance/décroissance)
        if len(close_prices) > self.ema_short_length:
            self.previous_ema_short = self._calculate_ema(close_prices[:-1], self.ema_short_length)
        else:
            self.previous_ema_short = None

        # RSI
        self.rsi = self._calculate_rsi(close_prices, self.rsi_length)

        # DMI et ADX
        self.plus_di, self.minus_di, self.adx = self._calculate_dmi_adx(
            candles_list, self.adx_length, self.adx_smoothing
        )

    def _update_trend_state(self):
        """Met à jour l'état de la tendance"""
        # Sauvegarder les états précédents
        self.previous_strong_up_trend = self.strong_up_trend
        self.previous_strong_down_trend = self.strong_down_trend

        # Vérifier que tous les indicateurs sont calculés
        if (self.ema_short is None or self.ema_long is None or
            self.rsi is None or self.adx is None or
            self.plus_di is None or self.minus_di is None or
            self.previous_ema_short is None):
            self.strong_up_trend = False
            self.strong_down_trend = False
            self.current_structure = None
            return

        # Détection de tendance haussière forte
        self.strong_up_trend = (
            self.ema_short > self.ema_long and
            self.plus_di > self.minus_di and
            self.rsi > self.rsi_up_threshold and
            self.adx > self.adx_trend_threshold and
            self.ema_short > self.previous_ema_short
        )

        # Détection de tendance baissière forte
        self.strong_down_trend = (
            self.ema_short < self.ema_long and
            self.minus_di > self.plus_di and
            self.rsi < self.rsi_down_threshold and
            self.adx > self.adx_trend_threshold and
            self.ema_short < self.previous_ema_short
        )

        # Mise à jour de la structure
        if self.strong_up_trend:
            self.current_structure = "bullish"
        elif self.strong_down_trend:
            self.current_structure = "bearish"
        else:
            self.current_structure = None

    def check_breakout(self, current_price, timestamp=None):
        """
        Vérifie les signaux de trading basés sur les changements de tendance.

        Args:
            current_price: Prix actuel
            timestamp: Timestamp optionnel (pour compatibilité)

        Returns:
            "BUY", "SELL" ou None
        """
        # Début de tendance haussière
        if self.strong_up_trend and not self.previous_strong_up_trend:
            self.last_signal = "BUY"
            self.signal_count["BUY"] += 1
            return "BUY"

        # Fin de tendance haussière uniquement
        if self.previous_strong_up_trend and not self.strong_up_trend:
            self.last_signal = "SELL"
            self.signal_count["SELL"] += 1
            return "SELL"

        return None

    def get_status(self):
        """Retourne le statut actuel de la stratégie"""
        return {
            'structure': self.current_structure,
            'strong_up_trend': self.strong_up_trend,
            'strong_down_trend': self.strong_down_trend,
            'last_signal': self.last_signal,
            'signal_count': self.signal_count,
            'indicators': {
                'ema_short': self.ema_short,
                'ema_long': self.ema_long,
                'rsi': self.rsi,
                'adx': self.adx,
                'plus_di': self.plus_di,
                'minus_di': self.minus_di
            },
            'candles_count': len(self.candles)
        }


class Bot:
    """
    Bot de trading modulaire supportant plusieurs stratégies configurables.
    Peut être lancé dans un thread séparé et géré par le dashboard.
    """

    def __init__(self, symbol: str, interval: str = "1m",
                 risk_pct: float = 0.1, max_pos: float = 0.0,
                 testnet: bool = True, dry_run: bool = True,
                 api_key: str = "", api_secret: str = "",
                 strategy_name: str = "trend_phase",
                 strategy_params: Optional[Dict[str, Any]] = None):
        self.symbol = symbol
        self.interval = interval
        self.risk_pct = risk_pct
        self.max_pos = max_pos
        self.testnet = testnet
        self.dry_run = dry_run
        self.api_key = api_key
        self.api_secret = api_secret
        self.strategy_name = strategy_name
        self.strategy_params = strategy_params or {}

        # État de la position
        self.pos_side = "FLAT"  # FLAT | LONG
        self.pos_qty = 0.0
        self.entry_price = 0.0

        # Stratégie - Instanciée de manière configurable
        self.strategy = create_strategy(
            strategy_name=strategy_name,
            timeframe=interval,
            **self.strategy_params
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
        insert_log(self.symbol, "INFO",
                  f"Bot démarré (stratégie={self.strategy_name}, testnet={self.testnet}, dry_run={self.dry_run})")

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

            # Ajouter toutes les bougies historiques
            for kline in klines:
                candle = {
                    'timestamp': kline[0],
                    'open': float(kline[1]),
                    'high': float(kline[2]),
                    'low': float(kline[3]),
                    'close': float(kline[4]),
                    'volume': float(kline[5])
                }
                self.strategy.update(candle)

            status = self.strategy.get_status()

            insert_log(self.symbol, "INFO",
                      f"Stratégie '{self.strategy_name}' initialisée: "
                      f"{status.get('structure') or 'Non détectée'}, "
                      f"bougies chargées: {status.get('candles_count', 0)}")

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
                    current_time = kline['t']  # timestamp en millisecondes

                    # Vérifier breakout sur chaque tick (avec cooldown)
                    signal_cooldown_ms = 10 * 60 * 1000  # 10 minutes en ms
                    time_since_last = current_time - self.last_signal_time

                    if time_since_last >= signal_cooldown_ms:
                        signal = self.strategy.check_breakout(current_close)
                        if signal:
                            self.last_signal_time = current_time
                            await self._execute_signal(signal, current_close)

                    # Traiter bougie fermée
                    if kline['x']:  # Bougie fermée
                        candle = {
                            'timestamp': kline['t'],
                            'open': float(kline['o']),
                            'high': float(kline['h']),
                            'low': float(kline['l']),
                            'close': float(kline['c']),
                            'volume': float(kline['v'])
                        }
                        self.strategy.update(candle)

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
