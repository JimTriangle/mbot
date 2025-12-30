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
