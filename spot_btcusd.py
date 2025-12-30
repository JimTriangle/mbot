from binance import AsyncClient, BinanceSocketManager
from binance.exceptions import BinanceAPIException, BinanceRequestException
from dotenv import load_dotenv
from time import strftime, localtime
import asyncio
import os
from collections import deque

load_dotenv()

API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
isTestnet = os.getenv("TESTNET", "False").lower() == "true"
isDryRun = os.getenv("DRY_RUN", "False").lower() == "true"

# Configuration
SYMBOL = "BTCUSDT"
KLINE_INTERVAL = "1m"

# Parametres pivots (on garde right pour la fiabilite)
PIVOT_LEFT = 3
PIVOT_RIGHT = 3

#  NOUVEAU : Strategie de BREAKOUT
USE_BREAKOUT_STRATEGY = True # Trade sur breakout du dernier pivot
BREAKOUT_THRESHOLD = 0.05  # 0.05% au-dessus/en-dessous du pivot

# Filtres
MIN_STRUCTURE_STRENGTH = 0.3
MIN_PIVOT_DISTANCE = 20

# Confirmation
USE_HIGHER_TIMEFRAME = True
HIGHER_TIMEFRAME = "15m"

SIGNAL_COOLDOWN = 10
WEBSOCKET_TIMEOUT = 60
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY = 5

is_running = True
last_signal_time = 0

class ThreeSwingsStrategy:
    """Strategie 3 swings avec detection ReALISTE"""
    
    def __init__(self, left=3, right=3, max_candles=200, timeframe="1m", min_pivot_distance=20):
        self.left = left
        self.right = right
        self.max_candles = max_candles
        self.timeframe = timeframe
        self.min_pivot_distance = min_pivot_distance
        
        self.candles = deque(maxlen=max_candles)
        
        # Pivots confirmes (avec lag)
        self.low1 = None
        self.low2 = None
        self.low3 = None
        self.high1 = None
        self.high2 = None
        self.high3 = None
        
        self.low1_time = None
        self.high1_time = None
        
        # etat structure
        self.current_structure = None
        self.last_signal = None
        self.signal_count = {"BUY": 0, "SELL": 0}
        self.false_signals = 0
        
        #  NOUVEAU : Niveaux de breakout
        self.buy_level = Non # Niveau e casser pour BUY
        self.sell_level = Non# Niveau e casser pour SELL
        
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
        """
         ReALISTE : Detecte les pivots CONFIRMeS (avec right bougies de lag)
        """
        if len(self.candles) < self.left + self.right + 1:
            return
            
        #  Important : On verifie la bougie qui a right bougies de confirmations
        check_index = len(self.candles) - self.right - 1
        
        pivot_low_data = self.detect_pivot_low(check_index)
        if pivot_low_data is not None:
            pivot_low, timestamp = pivot_low_data
            self.low3 = self.low2
            self.low2 = self.low1
            self.low1 = pivot_low
            self.low1_time = timestamp
            print(f"    Pivot BAS confirme: {pivot_low:.2f} (lag: {self.right} bougies)")
            
        pivot_high_data = self.detect_pivot_high(check_index)
        if pivot_high_data is not None:
            pivot_high, timestamp = pivot_high_data
            self.high3 = self.high2
            self.high2 = self.high1
            self.high1 = pivot_high
            self.high1_time = timestamp
            print(f"    Pivot HAUT confirme: {pivot_high:.2f} (lag: {self.right} bougies)")
    
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
            
    def analyze_structure(self):
        """Analyse structure (avec lag accepte)"""
        have_3_lows = all(x is not None for x in [self.low1, self.low2, self.low3])
        have_3_highs = all(x is not None for x in [self.high1, self.high2, self.high3])
        
        if not (have_3_lows and have_3_highs):
            return None
        
        strength = self.calculate_structure_strength()
        if strength < MIN_STRUCTURE_STRENGTH:
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
    
    def update_breakout_levels(self):
        """
         NOUVEAU : Definit les niveaux de breakout EN TEMPS ReEL
        """
        if not USE_BREAKOUT_STRATEGY:
            return
        
        structure = self.analyze_structure()
        
        if structure == "bullish" and self.high1:
            # Structure haussiere : on attend un breakout au-dessus du dernier pivot haut
            self.buy_level = self.high1 * (1 + BREAKOUT_THRESHOLD / 100)
            self.sell_level = None
            
        elif structure == "bearish" and self.low1:
            # Structure baissiere : on attend un breakout en-dessous du dernier pivot bas
            self.sell_level = self.low1 * (1 - BREAKOUT_THRESHOLD / 100)
            self.buy_level = None
            
        else:
            self.buy_level = None
            self.sell_level = None
    
    def check_breakout(self, current_price):
        """
         NOUVEAU : Verifie si le prix actuel casse un niveau
        CETTE FONCTION UTILISE UNIQUEMENT LE PReSENT
        """
        global last_signal_time
        
        if not USE_BREAKOUT_STRATEGY:
            return None
        
        # Verifier cooldown
        current_time = list(self.candles)[-1]['timestamp'] / 1000 / 60
        time_since_last = current_time - last_signal_time
        
        if time_since_last < SIGNAL_COOLDOWN:
            return None
        
        # BUY si prix casse le niveau haut
        if self.buy_level and current_price > self.buy_level:
            print(f"    BREAKOUT HAUSSIER ! Prix {current_price:.2f} > Niveau {self.buy_level:.2f}")
            self.last_signal = "BUY"
            self.signal_count["BUY"] += 1
            last_signal_time = current_time
            self.buy_level = Non# Reset niveau
            return "BUY"
        
        # SELL si prix casse le niveau bas
        if self.sell_level and current_price < self.sell_level:
            print(f"    BREAKOUT BAISSIER ! Prix {current_price:.2f} < Niveau {self.sell_level:.2f}")
            self.last_signal = "SELL"
            self.signal_count["SELL"] += 1
            last_signal_time = current_time
            self.sell_level = Non# Reset niveau
            return "SELL"
        
        return None
    
    def generate_signal_legacy(self):
        """
        L ANCIENNE VERSION : Signal sur changement de structure (avec lag)
        """
        global last_signal_time
        
        new_structure = self.analyze_structure()
        
        current_time = list(self.candles)[-1]['timestamp'] / 1000 / 60
        time_since_last = current_time - last_signal_time
        
        if time_since_last < SIGNAL_COOLDOWN:
            return None
        
        if new_structure != self.current_structure and new_structure is not None:
            old_structure = self.current_structure
            self.current_structure = new_structure
            
            if new_structure == "bullish" and old_structure != "bullish":
                self.last_signal = "BUY"
                self.signal_count["BUY"] += 1
                last_signal_time = current_time
                return "BUY"
            elif new_structure == "bearish" and old_structure != "bearish":
                self.last_signal = "SELL"
                self.signal_count["SELL"] += 1
                last_signal_time = current_time
                return "SELL"
                
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

strategy_main = ThreeSwingsStrategy(
    left=PIVOT_LEFT, 
    right=PIVOT_RIGHT, 
    timeframe=KLINE_INTERVAL,
    min_pivot_distance=MIN_PIVOT_DISTANCE
)

strategy_higher = None
if USE_HIGHER_TIMEFRAME:
    strategy_higher = ThreeSwingsStrategy(
        left=PIVOT_LEFT, 
        right=PIVOT_RIGHT, 
        timeframe=HIGHER_TIMEFRAME,
        min_pivot_distance=MIN_PIVOT_DISTANCE * 3
    )

async def get_historical_klines(client, interval, limit=200):
    try:
        klines = await client.get_klines(symbol=SYMBOL, interval=interval, limit=limit)
        
        candles_data = []
        for kline in klines:
            candles_data.append({
                'timestamp': kline[0],
                'open': float(kline[1]),
                'high': float(kline[2]),
                'low': float(kline[3]),
                'close': float(kline[4]),
                'volume': float(kline[5])
            })
        
        return candles_data
        
    except Exception as e:
        print(f"L Erreur: {e}")
        return None

async def initialize_strategies(client):
    print(f"\n=' Initialisation strategie {KLINE_INTERVAL}...")
    candles = await get_historical_klines(client, KLINE_INTERVAL, limit=200)
    
    if not candles:
        return False
        
    for candle in candles:
        strategy_main.add_candle(
            candle['timestamp'],
            candle['open'],
            candle['high'],
            candle['low'],
            candle['close'],
            candle['volume']
        )
    
    print(f"= Scan des pivots (avec lag de {PIVOT_RIGHT} bougies)...")
    pivot_count_high = 0
    pivot_count_low = 0
    
    for i in range(PIVOT_LEFT, len(strategy_main.candles) - PIVOT_RIGHT):
        pivot_low_data = strategy_main.detect_pivot_low(i)
        if pivot_low_data is not None:
            pivot_low, timestamp = pivot_low_data
            strategy_main.low3 = strategy_main.low2
            strategy_main.low2 = strategy_main.low1
            strategy_main.low1 = pivot_low
            strategy_main.low1_time = timestamp
            pivot_count_low += 1
            
        pivot_high_data = strategy_main.detect_pivot_high(i)
        if pivot_high_data is not None:
            pivot_high, timestamp = pivot_high_data
            strategy_main.high3 = strategy_main.high2
            strategy_main.high2 = strategy_main.high1
            strategy_main.high1 = pivot_high
            strategy_main.high1_time = timestamp
            pivot_count_high += 1
    
    print(f" Pivots: {pivot_count_high} hauts, {pivot_count_low} bas")
    
    strategy_main.current_structure = strategy_main.analyze_structure()
    strategy_main.update_breakout_levels()
    
    status = strategy_main.get_status()
    print(f" Structure {KLINE_INTERVAL}: {status['structure'] or 'Non detectee'}")
    print(f" Force: {status['strength']:.2f}%")
    
    if USE_BREAKOUT_STRATEGY:
        if status['breakout_levels']['buy']:
            print(f" Niveau BUY: {status['breakout_levels']['buy']:.2f}")
        if status['breakout_levels']['sell']:
            print(f" Niveau SELL: {status['breakout_levels']['sell']:.2f}")
    
    if USE_HIGHER_TIMEFRAME and strategy_higher:
        print(f"\n=' Initialisation strategie {HIGHER_TIMEFRAME}...")
        candles_higher = await get_historical_klines(client, HIGHER_TIMEFRAME, limit=200)
        
        if candles_higher:
            for candle in candles_higher:
                strategy_higher.add_candle(
                    candle['timestamp'],
                    candle['open'],
                    candle['high'],
                    candle['low'],
                    candle['close'],
                    candle['volume']
                )
            
            for i in range(PIVOT_LEFT, len(strategy_higher.candles) - PIVOT_RIGHT):
                pivot_low_data = strategy_higher.detect_pivot_low(i)
                if pivot_low_data is not None:
                    pivot_low, timestamp = pivot_low_data
                    strategy_higher.low3 = strategy_higher.low2
                    strategy_higher.low2 = strategy_higher.low1
                    strategy_higher.low1 = pivot_low
                    strategy_higher.low1_time = timestamp
                    
                pivot_high_data = strategy_higher.detect_pivot_high(i)
                if pivot_high_data is not None:
                    pivot_high, timestamp = pivot_high_data
                    strategy_higher.high3 = strategy_higher.high2
                    strategy_higher.high2 = strategy_higher.high1
                    strategy_higher.high1 = pivot_high
                    strategy_higher.high1_time = timestamp
            
            strategy_higher.current_structure = strategy_higher.analyze_structure()
            
            status_higher = strategy_higher.get_status()
            print(f" Structure {HIGHER_TIMEFRAME}: {status_higher['structure'] or 'Non detectee'}")
    
    return True

async def execute_trade_signal(signal, price):
    confirmed = True
    if USE_HIGHER_TIMEFRAME and strategy_higher:
        higher_structure = strategy_higher.current_structure
        
        if signal == "BUY" and higher_structure == "bearish":
            confirmed = False
            print(f"   Signal BUY NON CONFIRMe par {HIGHER_TIMEFRAME}")
        elif signal == "SELL" and higher_structure == "bullish":
            confirmed = False
            print(f"   Signal SELL NON CONFIRMe par {HIGHER_TIMEFRAME}")
    
    if not confirmed:
        strategy_main.false_signals += 1
        return
    
    emoji = "" if signal == "BUY" else "=4"
    action = "ACHAT" if signal == "BUY" else "VENTE"
    
    status = strategy_main.get_status()
    
    print(f"\n{'='*70}")
    print(f"{emoji} SIGNAL {action} CONFIRMe!")
    print(f"   Prix: {price:.2f} USDT")
    print(f"   Type: {'BREAKOUT' if USE_BREAKOUT_STRATEGY else 'STRUCTURE'}")
    print(f"   Structure: {status['structure']}")
    print(f"   Force: {status['strength']:.2f}%")
    print(f"   Total BUY: {status['signal_count']['BUY']} | SELL: {status['signal_count']['SELL']}")
    
    if isDryRun:
        print(f"   MODE DRY-RUN")
    
    print(f"{'='*70}\n")

async def handle_kline_socket_with_reconnect():
    reconnect_count = 0
    
    while is_running:
        client = None
        try:
            client = await AsyncClient.create(API_KEY, API_SECRET, testnet=isTestnet)
            bsm = BinanceSocketManager(client)
            ks = bsm.kline_socket(SYMBOL, interval=KLINE_INTERVAL)
            
            if reconnect_count > 0:
                print(f"= Reconnexion reussie")
            
            reconnect_count = 0
            print(f" WebSocket {SYMBOL} ({KLINE_INTERVAL}) actif")
            
            async with ks as kscm:
                while is_running:
                    try:
                        msg = await asyncio.wait_for(kscm.recv(), timeout=WEBSOCKET_TIMEOUT)
                        
                        if not msg or 'k' not in msg:
                            continue
                        
                        kline = msg['k']
                        
                        if not kline or 'x' not in kline:
                            continue
                        
                        #  Verifier breakout sur CHAQUE bougie (temps reel)
                        current_close = float(kline['c'])
                        
                        if USE_BREAKOUT_STRATEGY:
                            signal = strategy_main.check_breakout(current_close)
                            if signal:
                                await execute_trade_signal(signal, current_close)
                        
                        # Traiter bougie fermee
                        is_closed = kline['x']
                        
                        if is_closed:
                            timestamp = kline['t']
                            open_price = float(kline['o'])
                            high_price = float(kline['h'])
                            low_price = float(kline['l'])
                            close_price = float(kline['c'])
                            volume = float(kline['v'])
                            time_str = strftime('%H:%M:%S', localtime(timestamp / 1000))
                            
                            strategy_main.add_candle(timestamp, open_price, high_price, low_price, close_price, volume)
                            strategy_main.update_pivots()
                            strategy_main.current_structure = strategy_main.analyze_structure()
                            strategy_main.update_breakout_levels()
                            
                            # Signal legacy (si breakout desactive)
                            if not USE_BREAKOUT_STRATEGY:
                                signal = strategy_main.generate_signal_legacy()
                                if signal:
                                    await execute_trade_signal(signal, close_price)
                            
                            change = ((close_price - open_price) / open_price) * 100
                            emoji = "" if change > 0 else "=4"
                            
                            print(f"{emoji} [{time_str}] {close_price:.2f} USDT ({change:+.2f}%)", end="")
                            
                            status = strategy_main.get_status()
                            if status['structure']:
                                structure_emoji = "" if status['structure'] == "bullish" else ""
                                print(f" | {structure_emoji} {status['structure']}", end="")
                            
                            if status['breakout_levels']['buy']:
                                print(f" | BUY@{status['breakout_levels']['buy']:.0f}", end="")
                            if status['breakout_levels']['sell']:
                                print(f" | SELL@{status['breakout_levels']['sell']:.0f}", end="")
                            
                            print()
                    
                    except asyncio.TimeoutError:
                        continue
                    except KeyError as e:
                        continue
                    except Exception as e:
                        print(f"Erreur: {e}")
                        continue
        
        except Exception as e:
            reconnect_count += 1
            print(f"\nDeconnexion: {e}")
            
            if reconnect_count >= MAX_RECONNECT_ATTEMPTS:
                print(f"L echec apres {MAX_RECONNECT_ATTEMPTS} tentatives")
                break
            
            print(f"= Reconnexion dans {RECONNECT_DELAY}s...")
            await asyncio.sleep(RECONNECT_DELAY)
        
        finally:
            if client:
                try:
                    await client.close_connection()
                except:
                    pass

async def handle_higher_timeframe_socket_with_reconnect():
    if not USE_HIGHER_TIMEFRAME or not strategy_higher:
        return
    
    reconnect_count = 0
    
    while is_running:
        client = None
        try:
            client = await AsyncClient.create(API_KEY, API_SECRET, testnet=isTestnet)
            bsm = BinanceSocketManager(client)
            ks = bsm.kline_socket(SYMBOL, interval=HIGHER_TIMEFRAME)
            
            reconnect_count = 0
            
            async with ks as kscm:
                while is_running:
                    try:
                        msg = await asyncio.wait_for(kscm.recv(), timeout=WEBSOCKET_TIMEOUT)
                        
                        if not msg or 'k' not in msg:
                            continue
                        
                        kline = msg['k']
                        
                        if not kline or 'x' not in kline:
                            continue
                        
                        is_closed = kline['x']
                        
                        if is_closed:
                            timestamp = kline['t']
                            open_price = float(kline['o'])
                            high_price = float(kline['h'])
                            low_price = float(kline['l'])
                            close_price = float(kline['c'])
                            volume = float(kline['v'])
                            
                            strategy_higher.add_candle(timestamp, open_price, high_price, low_price, close_price, volume)
                            strategy_higher.update_pivots()
                            strategy_higher.current_structure = strategy_higher.analyze_structure()
                            
                            status = strategy_higher.get_status()
                            time_str = strftime('%H:%M', localtime(timestamp / 1000))
                            print(f"= [{time_str}] {HIGHER_TIMEFRAME} Structure: {status['structure']}")
                    
                    except asyncio.TimeoutError:
                        continue
                    except:
                        continue
        
        except Exception as e:
            reconnect_count += 1
            if reconnect_count < MAX_RECONNECT_ATTEMPTS:
                await asyncio.sleep(RECONNECT_DELAY)
            else:
                break
        
        finally:
            if client:
                try:
                    await client.close_connection()
                except:
                    pass

async def main():
    global is_running
    client = None
    
    try:
        if not API_KEY or not API_SECRET:
            print("L Cles API manquantes")
            return
        
        mode = "TESTNET" if isTestnet else "PRODUCTION"
        dry_run_text = " (DRY-RUN)" if isDryRun else ""
        
        print(f"\n{'='*70}")
        print(f"> BOT 3 SWINGS - VERSION ReALISTE")
        print(f"   Symbole: {SYMBOL}")
        print(f"   Timeframe: {KLINE_INTERVAL}")
        if USE_HIGHER_TIMEFRAME:
            print(f"   Confirmation: {HIGHER_TIMEFRAME}")
        print(f"   Strategie: {'BREAKOUT (temps reel)' if USE_BREAKOUT_STRATEGY else 'STRUCTURE (avec lag)'}")
        print(f"   Lag pivots: {PIVOT_RIGHT} bougies ({PIVOT_RIGHT} min)")
        print(f"   Mode: {mode}{dry_run_text}")
        print(f"{'='*70}")
        
        print("\n Connexion...")
        client = await AsyncClient.create(API_KEY, API_SECRET, testnet=isTestnet)
        print(" Connecte")
        
        success = await initialize_strategies(client)
        if not success:
            return
        
        await client.close_connection()
        client = None
        
        if isDryRun:
            print("\nMODE DRY-RUN ACTIVe\n")
        
        print(" Demarrage...\n")
        
        tasks = [
            asyncio.create_task(handle_kline_socket_with_reconnect())
        ]
        
        if USE_HIGHER_TIMEFRAME:
            tasks.append(asyncio.create_task(handle_higher_timeframe_socket_with_reconnect()))
        
        await asyncio.gather(*tasks)
        
        print("\n Bot arrete")
        
    except KeyboardInterrupt:
        print("\nArret...")
        is_running = False
    except Exception as e:
        print(f"\nL Erreur: {e}")
    finally:
        if client:
            await client.close_connection()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n=K Au revoir!")