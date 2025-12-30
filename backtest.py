"""
Module de backtesting pour la stratégie 3 Swings
Permet de simuler la stratégie sur des données historiques
et d'analyser les performances
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from binance import AsyncClient
import pandas as pd
import numpy as np
from bot_core import ThreeSwingsStrategy


class BacktestEngine:
    """Moteur de backtesting pour la stratégie 3 Swings"""

    def __init__(
        self,
        symbol: str,
        interval: str,
        risk_pct: float = 1.0,
        max_pos: float = 1000.0,
        testnet: bool = True,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None
    ):
        """
        Initialize backtest engine

        Args:
            symbol: Trading pair (ex: BTCUSDT)
            interval: Timeframe (1m, 5m, 15m, 1h, etc.)
            risk_pct: Percentage of capital to risk per trade
            max_pos: Maximum position size in quote currency
            testnet: Use testnet API
            api_key: Binance API key
            api_secret: Binance API secret
        """
        self.symbol = symbol
        self.interval = interval
        self.risk_pct = risk_pct
        self.max_pos = max_pos
        self.testnet = testnet
        self.api_key = api_key
        self.api_secret = api_secret

        # Strategy instance
        self.strategy = ThreeSwingsStrategy(
            left=3,
            right=3,
            max_candles=200,
            timeframe=interval,
            min_pivot_distance=20
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

        Args:
            start_date: Start date for backtest
            end_date: End date for backtest

        Returns:
            List of candles with OHLCV data
        """
        if self.testnet:
            client = await AsyncClient.create(
                api_key=self.api_key,
                api_secret=self.api_secret,
                testnet=True
            )
        else:
            client = await AsyncClient.create(
                api_key=self.api_key,
                api_secret=self.api_secret
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

            # Convert to our format
            candles = []
            for k in klines:
                candle = {
                    'timestamp': int(k[0]),
                    'open': float(k[1]),
                    'high': float(k[2]),
                    'low': float(k[3]),
                    'close': float(k[4]),
                    'volume': float(k[5]),
                }
                candles.append(candle)

            return candles

        finally:
            await client.close_connection()

    def _calculate_position_size(self, price: float) -> float:
        """Calculate position size based on risk and capital"""
        # Simple approach: use risk_pct of current capital
        risk_amount = self.current_capital * (self.risk_pct / 100.0)
        qty = risk_amount / price

        # Cap at max position value
        max_qty = self.max_pos / price
        qty = min(qty, max_qty)

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
        """Record current breakout levels"""
        if self.strategy.buy_level is not None:
            self.breakout_levels.append({
                'type': 'BUY',
                'level': self.strategy.buy_level,
                'timestamp': timestamp,
                'datetime': datetime.fromtimestamp(timestamp / 1000).isoformat()
            })

        if self.strategy.sell_level is not None:
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
        self.strategy = ThreeSwingsStrategy(
            left=3,
            right=3,
            max_candles=200,
            timeframe=self.interval,
            min_pivot_distance=20
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

            # Record pivots when they're confirmed
            if self.strategy.high1 is not None and self.strategy.high1_time is not None:
                # Check if this is a newly confirmed pivot
                if not any(p['timestamp'] == self.strategy.high1_time and p['type'] == 'HIGH' for p in self.pivot_history):
                    self._record_pivot('HIGH', self.strategy.high1, self.strategy.high1_time, i)

            if self.strategy.low1 is not None and self.strategy.low1_time is not None:
                # Check if this is a newly confirmed pivot
                if not any(p['timestamp'] == self.strategy.low1_time and p['type'] == 'LOW' for p in self.pivot_history):
                    self._record_pivot('LOW', self.strategy.low1, self.strategy.low1_time, i)

            # Record breakout levels
            self._record_breakout_levels(timestamp)

            # Check for signals (with cooldown)
            if timestamp - self.last_signal_time >= self.signal_cooldown:
                signal = self.strategy.check_breakout(close_price, timestamp)

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
    risk_pct: float = 1.0,
    max_pos: float = 1000.0,
    initial_capital: float = 10000.0,
    testnet: bool = True,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None
) -> Dict:
    """
    Convenience function to run a complete backtest

    Args:
        symbol: Trading pair
        interval: Timeframe
        start_date: Start date
        end_date: End date
        risk_pct: Risk percentage per trade
        max_pos: Maximum position size
        initial_capital: Starting capital
        testnet: Use testnet API
        api_key: Binance API key
        api_secret: Binance API secret

    Returns:
        Complete backtest results with trades, statistics, and visualization data
    """
    engine = BacktestEngine(
        symbol=symbol,
        interval=interval,
        risk_pct=risk_pct,
        max_pos=max_pos,
        testnet=testnet,
        api_key=api_key,
        api_secret=api_secret
    )

    # Fetch historical data
    candles = await engine.fetch_historical_data(start_date, end_date)

    # Run backtest
    results = engine.run_backtest(candles, initial_capital)

    return results
