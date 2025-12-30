"""
Module de backtesting pour les stratégies de trading
Permet de simuler les stratégies sur des données historiques
et d'analyser les performances
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from binance import AsyncClient
import pandas as pd
import numpy as np
from strategies import create_strategy


class BacktestEngine:
    """Moteur de backtesting pour les stratégies de trading"""

    def __init__(
        self,
        symbol: str,
        interval: str,
        allocation_pct: float = 10.0,
        testnet: bool = True,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        strategy_name: str = "trend_phase",
        strategy_params: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize backtest engine

        Args:
            symbol: Trading pair (ex: BTCUSDT)
            interval: Timeframe (1m, 5m, 15m, 1h, etc.)
            allocation_pct: Percentage of available capital to allocate per trade (e.g., 10.0 = 10%)
            testnet: Use testnet API
            api_key: Binance API key
            api_secret: Binance API secret
            strategy_name: Name of the strategy to use
            strategy_params: Parameters for the strategy
        """
        self.symbol = symbol
        self.interval = interval
        self.allocation_pct = allocation_pct
        self.testnet = testnet
        self.api_key = api_key
        self.api_secret = api_secret
        self.strategy_name = strategy_name
        self.strategy_params = strategy_params or {}

        # Strategy instance
        self.strategy = create_strategy(
            strategy_name=strategy_name,
            timeframe=interval,
            **self.strategy_params
        )

        # Position tracking
        self.pos_side = "FLAT"
        self.pos_qty = 0.0
        self.entry_price = 0.0
        self.entry_time = None

        # Trade history
        self.trades: List[Dict] = []

        # Price data
        self.price_data: List[Dict] = []

        # Pivot history for visualization
        self.pivot_history: List[Dict] = []

        # Breakout level history
        self.breakout_levels: List[Dict] = []

        # Signal cooldown
        self.last_signal_time = 0
        self.signal_cooldown = 10 * 60 * 1000  # 10 minutes in ms

        # Initial capital
        self.initial_capital = 10000.0  # Default $10,000
        self.current_capital = self.initial_capital

    async def fetch_historical_data(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """
        Fetch historical kline data from Binance

        IMPORTANT: Always uses PRODUCTION API for real historical data,
        regardless of testnet setting. The testnet parameter only affects
        trade execution, not historical data retrieval.

        Args:
            start_date: Start date for backtest
            end_date: End date for backtest

        Returns:
            List of candles with OHLCV data
        """
        # ALWAYS use production API for real historical data
        client = await AsyncClient.create(
            api_key=self.api_key,
            api_secret=self.api_secret,
            testnet=False  # Force production for historical data
        )

        try:
            # Convert dates to milliseconds
            start_ms = int(start_date.timestamp() * 1000)
            end_ms = int(end_date.timestamp() * 1000)

            # Fetch klines
            klines = await client.get_historical_klines(
                self.symbol,
                self.interval,
                start_ms,
                end_ms
            )

            # Convert to our format with validation
            candles = []
            invalid_count = 0

            for k in klines:
                try:
                    candle = {
                        'timestamp': int(k[0]),
                        'open': float(k[1]),
                        'high': float(k[2]),
                        'low': float(k[3]),
                        'close': float(k[4]),
                        'volume': float(k[5]),
                    }

                    # Validate candle data
                    if not self._is_valid_candle(candle):
                        invalid_count += 1
                        continue

                    candles.append(candle)

                except (ValueError, IndexError) as e:
                    # Skip malformed candles
                    invalid_count += 1
                    continue

            if invalid_count > 0:
                print(f"⚠️ Warning: {invalid_count} invalid candles filtered out")

            return candles

        finally:
            await client.close_connection()

    def _is_valid_candle(self, candle: Dict) -> bool:
        """
        Validate candle data to filter out corrupted or unrealistic values

        Args:
            candle: Candle dictionary with OHLCV data

        Returns:
            True if candle is valid, False otherwise
        """
        try:
            o, h, l, c, v = candle['open'], candle['high'], candle['low'], candle['close'], candle['volume']

            # Check for None, NaN, or infinite values
            if any(x is None or np.isnan(x) or np.isinf(x) for x in [o, h, l, c, v]):
                return False

            # Check for negative or zero prices
            if any(x <= 0 for x in [o, h, l, c]):
                return False

            # Validate OHLC relationship: high >= low, high >= open/close, low <= open/close
            if h < l:
                return False
            if h < max(o, c) or l > min(o, c):
                return False

            # Check for extreme price movements (likely data corruption)
            # A candle with > 10x range (high/low > 10) is suspicious
            if h / l > 10.0:
                return False

            # Check for extreme outlier prices
            # If the price range within a single candle is > 500% of the low, it's suspicious
            price_range = h - l
            if price_range > (l * 5.0):
                return False

            return True

        except (KeyError, TypeError, ZeroDivisionError):
            return False

    def _calculate_position_size(self, price: float) -> float:
        """Calculate position size based on allocation percentage of available capital"""
        # Simple allocation: use allocation_pct of current capital
        allocation_amount = self.current_capital * (self.allocation_pct / 100.0)
        qty = allocation_amount / price

        return qty

    def _execute_buy(self, price: float, timestamp: int):
        """Execute a buy signal"""
        if self.pos_side != "FLAT":
            return

        qty = self._calculate_position_size(price)
        quote_qty = qty * price

        # Record trade
        trade = {
            'symbol': self.symbol,
            'side': 'BUY',
            'qty': qty,
            'price': price,
            'quote_qty': quote_qty,
            'timestamp': timestamp,
            'datetime': datetime.fromtimestamp(timestamp / 1000).isoformat(),
            'pnl': 0.0,
            'pnl_pct': 0.0
        }
        self.trades.append(trade)

        # Update position
        self.pos_side = "LONG"
        self.pos_qty = qty
        self.entry_price = price
        self.entry_time = timestamp

        # Deduct from capital (simulated)
        self.current_capital -= quote_qty

    def _execute_sell(self, price: float, timestamp: int):
        """Execute a sell signal"""
        if self.pos_side != "LONG":
            return

        qty = self.pos_qty
        quote_qty = qty * price

        # Calculate PnL
        pnl = (price - self.entry_price) * qty
        pnl_pct = ((price - self.entry_price) / self.entry_price) * 100

        # Record trade
        trade = {
            'symbol': self.symbol,
            'side': 'SELL',
            'qty': qty,
            'price': price,
            'quote_qty': quote_qty,
            'timestamp': timestamp,
            'datetime': datetime.fromtimestamp(timestamp / 1000).isoformat(),
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'entry_price': self.entry_price,
            'entry_time': datetime.fromtimestamp(self.entry_time / 1000).isoformat(),
            'hold_time_hours': (timestamp - self.entry_time) / (1000 * 60 * 60)
        }
        self.trades.append(trade)

        # Update position
        self.pos_side = "FLAT"
        self.pos_qty = 0.0
        self.entry_price = 0.0
        self.entry_time = None

        # Add to capital (simulated)
        self.current_capital += quote_qty

    def _record_pivot(self, pivot_type: str, price: float, timestamp: int, index: int):
        """Record a pivot for visualization"""
        self.pivot_history.append({
            'type': pivot_type,  # 'HIGH' or 'LOW'
            'price': price,
            'timestamp': timestamp,
            'datetime': datetime.fromtimestamp(timestamp / 1000).isoformat(),
            'index': index
        })

    def _record_breakout_levels(self, timestamp: int):
        """Record current breakout levels (only for strategies that support it)"""
        # Check if strategy has breakout levels (e.g., ThreeSwingsStrategy)
        if hasattr(self.strategy, 'buy_level') and self.strategy.buy_level is not None:
            self.breakout_levels.append({
                'type': 'BUY',
                'level': self.strategy.buy_level,
                'timestamp': timestamp,
                'datetime': datetime.fromtimestamp(timestamp / 1000).isoformat()
            })

        if hasattr(self.strategy, 'sell_level') and self.strategy.sell_level is not None:
            self.breakout_levels.append({
                'type': 'SELL',
                'level': self.strategy.sell_level,
                'timestamp': timestamp,
                'datetime': datetime.fromtimestamp(timestamp / 1000).isoformat()
            })

    def run_backtest(
        self,
        candles: List[Dict],
        initial_capital: float = 10000.0
    ) -> Dict:
        """
        Run backtest on historical data

        Args:
            candles: List of historical candles
            initial_capital: Starting capital for simulation

        Returns:
            Dictionary with backtest results and statistics
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.trades = []
        self.pivot_history = []
        self.breakout_levels = []
        self.price_data = candles

        # Reset strategy
        self.strategy = create_strategy(
            strategy_name=self.strategy_name,
            timeframe=self.interval,
            **self.strategy_params
        )

        # Reset position
        self.pos_side = "FLAT"
        self.pos_qty = 0.0
        self.entry_price = 0.0
        self.entry_time = None
        self.last_signal_time = 0

        # Process each candle
        for i, candle in enumerate(candles):
            timestamp = candle['timestamp']
            close_price = candle['close']

            # Update strategy with closed candle
            self.strategy.update(candle)

            # Check for signals (with cooldown)
            if timestamp - self.last_signal_time >= self.signal_cooldown:
                signal = self.strategy.check_breakout(close_price)

                if signal == "BUY":
                    self._execute_buy(close_price, timestamp)
                    self.last_signal_time = timestamp

                elif signal == "SELL":
                    self._execute_sell(close_price, timestamp)
                    self.last_signal_time = timestamp

        # Close any open position at end
        if self.pos_side == "LONG":
            last_candle = candles[-1]
            self._execute_sell(last_candle['close'], last_candle['timestamp'])

        # Calculate statistics
        stats = self._calculate_statistics()

        return {
            'trades': self.trades,
            'pivots': self.pivot_history,
            'breakout_levels': self.breakout_levels,
            'price_data': self.price_data,
            'statistics': stats
        }

    def _calculate_statistics(self) -> Dict:
        """Calculate comprehensive backtest statistics"""
        if not self.trades:
            return {
                'total_trades': 0,
                'buy_orders': 0,
                'sell_orders': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'total_pnl_pct': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'largest_win': 0.0,
                'largest_loss': 0.0,
                'max_drawdown': 0.0,
                'max_drawdown_pct': 0.0,
                'profit_factor': 0.0,
                'avg_hold_time_hours': 0.0,
                'final_capital': self.current_capital,
                'return_pct': 0.0
            }

        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(self.trades)

        # Count orders
        buy_orders = len(df[df['side'] == 'BUY'])
        sell_orders = len(df[df['side'] == 'SELL'])

        # Get sell trades (closed positions with PnL)
        sells = df[df['side'] == 'SELL'].copy()

        if len(sells) == 0:
            return {
                'total_trades': len(self.trades),
                'buy_orders': buy_orders,
                'sell_orders': sell_orders,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'total_pnl_pct': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'largest_win': 0.0,
                'largest_loss': 0.0,
                'max_drawdown': 0.0,
                'max_drawdown_pct': 0.0,
                'profit_factor': 0.0,
                'avg_hold_time_hours': 0.0,
                'final_capital': self.current_capital,
                'return_pct': ((self.current_capital - self.initial_capital) / self.initial_capital) * 100
            }

        # Win/Loss analysis
        wins = sells[sells['pnl'] > 0]
        losses = sells[sells['pnl'] <= 0]

        winning_trades = len(wins)
        losing_trades = len(losses)
        win_rate = (winning_trades / len(sells)) * 100 if len(sells) > 0 else 0.0

        # PnL metrics
        total_pnl = sells['pnl'].sum()
        total_pnl_pct = ((self.current_capital - self.initial_capital) / self.initial_capital) * 100

        avg_win = wins['pnl'].mean() if len(wins) > 0 else 0.0
        avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0.0

        largest_win = wins['pnl'].max() if len(wins) > 0 else 0.0
        largest_loss = losses['pnl'].min() if len(losses) > 0 else 0.0

        # Profit factor
        gross_profit = wins['pnl'].sum() if len(wins) > 0 else 0.0
        gross_loss = abs(losses['pnl'].sum()) if len(losses) > 0 else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

        # Drawdown calculation
        sells['cumulative_pnl'] = sells['pnl'].cumsum()
        running_max = sells['cumulative_pnl'].cummax()
        drawdown = running_max - sells['cumulative_pnl']
        max_drawdown = drawdown.max() if len(drawdown) > 0 else 0.0

        # Calculate drawdown percentage
        peak_capital = self.initial_capital + running_max.max() if len(running_max) > 0 else self.initial_capital
        max_drawdown_pct = (max_drawdown / peak_capital) * 100 if peak_capital > 0 else 0.0

        # Average hold time
        avg_hold_time = sells['hold_time_hours'].mean() if 'hold_time_hours' in sells.columns else 0.0

        return {
            'total_trades': len(self.trades),
            'buy_orders': buy_orders,
            'sell_orders': sell_orders,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'total_pnl_pct': total_pnl_pct,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'largest_win': largest_win,
            'largest_loss': largest_loss,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown_pct,
            'profit_factor': profit_factor,
            'avg_hold_time_hours': avg_hold_time,
            'final_capital': self.current_capital,
            'return_pct': total_pnl_pct
        }


async def run_backtest_async(
    symbol: str,
    interval: str,
    start_date: datetime,
    end_date: datetime,
    allocation_pct: float = 10.0,
    initial_capital: float = 10000.0,
    testnet: bool = True,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    strategy_name: str = "trend_phase",
    strategy_params: Optional[Dict[str, Any]] = None
) -> Dict:
    """
    Convenience function to run a complete backtest

    Args:
        symbol: Trading pair
        interval: Timeframe
        start_date: Start date
        end_date: End date
        allocation_pct: Percentage of available capital to allocate per trade
        initial_capital: Starting capital
        testnet: Use testnet API
        api_key: Binance API key
        api_secret: Binance API secret
        strategy_name: Name of the strategy to use
        strategy_params: Parameters for the strategy

    Returns:
        Complete backtest results with trades, statistics, and visualization data
    """
    engine = BacktestEngine(
        symbol=symbol,
        interval=interval,
        allocation_pct=allocation_pct,
        testnet=testnet,
        api_key=api_key,
        api_secret=api_secret,
        strategy_name=strategy_name,
        strategy_params=strategy_params
    )

    # Fetch historical data
    candles = await engine.fetch_historical_data(start_date, end_date)

    # Run backtest
    results = engine.run_backtest(candles, initial_capital)

    return results
