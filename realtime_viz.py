"""
Module realtime_viz.py - Visualisation en temps réel des bots actifs.
Affiche les graphiques avec indicateurs techniques et signaux de trading.
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from binance import AsyncClient
from storage import fetch_positions, fetch_trades


async def fetch_realtime_klines(
    symbol: str,
    interval: str,
    lookback_candles: int = 200,
    api_key: str = "",
    api_secret: str = "",
    testnet: bool = True
) -> List[Dict]:
    """
    Récupère les klines récentes pour un symbole donné.

    Args:
        symbol: Symbole de trading (ex: BTCUSDT)
        interval: Intervalle des klines (1m, 5m, 1h, etc.)
        lookback_candles: Nombre de bougies à récupérer
        api_key: Clé API Binance
        api_secret: Secret API Binance
        testnet: Utiliser le testnet ou la production

    Returns:
        Liste de dictionnaires contenant les données OHLCV
    """
    client = await AsyncClient.create(
        api_key=api_key,
        api_secret=api_secret,
        testnet=testnet
    )

    try:
        # Calculer la date de début basée sur le nombre de bougies
        klines = await client.get_klines(
            symbol=symbol,
            interval=interval,
            limit=lookback_candles
        )

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


def calculate_ema(prices: List[float], period: int) -> Optional[float]:
    """Calcule l'EMA (Exponential Moving Average)"""
    if len(prices) < period:
        return None

    multiplier = 2 / (period + 1)
    ema = sum(prices[:period]) / period

    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema

    return ema


def calculate_ema_series(prices: List[float], period: int) -> List[Optional[float]]:
    """Calcule la série complète d'EMA"""
    ema_values = []

    for i in range(len(prices)):
        if i < period - 1:
            ema_values.append(None)
        else:
            ema = calculate_ema(prices[:i+1], period)
            ema_values.append(ema)

    return ema_values


def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
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


def calculate_rsi_series(prices: List[float], period: int = 14) -> List[Optional[float]]:
    """Calcule la série complète de RSI"""
    rsi_values = []

    for i in range(len(prices)):
        if i < period:
            rsi_values.append(None)
        else:
            rsi = calculate_rsi(prices[:i+1], period)
            rsi_values.append(rsi)

    return rsi_values


def calculate_adx_series(candles: List[Dict], adx_length: int = 14, smoothing: int = 14) -> tuple:
    """
    Calcule les séries ADX, DI+, DI-

    Returns:
        Tuple (adx_values, plus_di_values, minus_di_values)
    """
    if len(candles) < adx_length + smoothing + 1:
        return [None] * len(candles), [None] * len(candles), [None] * len(candles)

    # Calcul True Range
    tr_values = [None]  # Premier élément est None
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

    # Calcul Directional Movement
    plus_dm = [None]
    minus_dm = [None]

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

    # Lissage des valeurs (Wilder's smoothing)
    def smooth_values(values, period, start_idx):
        smoothed = [None] * start_idx
        if start_idx + period > len(values):
            return [None] * len(values)

        smoothed.append(sum([v for v in values[start_idx:start_idx+period] if v is not None]))

        for i in range(start_idx + period, len(values)):
            if values[i] is not None and smoothed[-1] is not None:
                smoothed_value = (smoothed[-1] * (period - 1) + values[i]) / period
                smoothed.append(smoothed_value)
            else:
                smoothed.append(None)

        return smoothed

    atr = smooth_values(tr_values, adx_length, 1)
    smoothed_plus_dm = smooth_values(plus_dm, adx_length, 1)
    smoothed_minus_dm = smooth_values(minus_dm, adx_length, 1)

    # Calcul DI+ et DI-
    plus_di_values = []
    minus_di_values = []

    for i in range(len(candles)):
        if atr[i] is not None and atr[i] != 0 and smoothed_plus_dm[i] is not None and smoothed_minus_dm[i] is not None:
            plus_di = (smoothed_plus_dm[i] / atr[i]) * 100
            minus_di = (smoothed_minus_dm[i] / atr[i]) * 100
            plus_di_values.append(plus_di)
            minus_di_values.append(minus_di)
        else:
            plus_di_values.append(None)
            minus_di_values.append(None)

    # Calcul DX et ADX
    dx_values = []
    for i in range(len(candles)):
        if plus_di_values[i] is not None and minus_di_values[i] is not None:
            di_sum = plus_di_values[i] + minus_di_values[i]
            if di_sum != 0:
                dx = abs(plus_di_values[i] - minus_di_values[i]) / di_sum * 100
                dx_values.append(dx)
            else:
                dx_values.append(None)
        else:
            dx_values.append(None)

    # ADX est la moyenne lissée de DX
    adx_values = smooth_values(dx_values, smoothing, adx_length)

    return adx_values, plus_di_values, minus_di_values


def create_realtime_chart(
    candles: List[Dict],
    symbol: str,
    interval: str,
    bot_position: Optional[Dict] = None,
    recent_trades: List[Dict] = None,
    ema_short_period: int = 20,
    ema_long_period: int = 50,
    rsi_period: int = 14,
    adx_period: int = 14,
    adx_smoothing: int = 14
) -> go.Figure:
    """
    Crée un graphique interactif en temps réel avec indicateurs techniques.

    Args:
        candles: Liste des bougies OHLCV
        symbol: Symbole de trading
        interval: Intervalle des bougies
        bot_position: Position actuelle du bot (dict avec 'side', 'qty', 'entry_price', 'current_price', 'pnl_unrealized')
        recent_trades: Liste des trades récents pour affichage
        ema_short_period: Période EMA courte
        ema_long_period: Période EMA longue
        rsi_period: Période RSI
        adx_period: Période ADX
        adx_smoothing: Lissage ADX

    Returns:
        Figure Plotly
    """
    if not candles:
        return go.Figure()

    # Conversion en DataFrame pour faciliter les calculs
    df = pd.DataFrame(candles)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

    # Calcul des indicateurs
    closes = df['close'].tolist()

    ema_short = calculate_ema_series(closes, ema_short_period)
    ema_long = calculate_ema_series(closes, ema_long_period)
    rsi = calculate_rsi_series(closes, rsi_period)
    adx, plus_di, minus_di = calculate_adx_series(candles, adx_period, adx_smoothing)

    # Création des subplots (4 lignes: Prix + EMA, RSI, ADX, P&L)
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.5, 0.15, 0.15, 0.2],
        subplot_titles=(
            f'{symbol} - {interval} - Temps Réel',
            'RSI (14)',
            'ADX / DMI (14)',
            'Position & P&L Non Réalisé'
        )
    )

    # 1. Candlestick Chart
    fig.add_trace(
        go.Candlestick(
            x=df['datetime'],
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='Prix',
            increasing_line_color='#26a69a',
            decreasing_line_color='#ef5350'
        ),
        row=1, col=1
    )

    # 2. EMA Court
    fig.add_trace(
        go.Scatter(
            x=df['datetime'],
            y=ema_short,
            mode='lines',
            name=f'EMA {ema_short_period}',
            line=dict(color='#2196F3', width=1.5)
        ),
        row=1, col=1
    )

    # 3. EMA Long
    fig.add_trace(
        go.Scatter(
            x=df['datetime'],
            y=ema_long,
            mode='lines',
            name=f'EMA {ema_long_period}',
            line=dict(color='#FF9800', width=1.5)
        ),
        row=1, col=1
    )

    # 4. Position actuelle (si existe)
    if bot_position and bot_position.get('side') == 'LONG':
        entry_price = bot_position.get('entry_price', 0)
        current_price = bot_position.get('current_price', df['close'].iloc[-1])

        # Ligne de prix d'entrée
        fig.add_hline(
            y=entry_price,
            line_dash="dash",
            line_color="yellow",
            annotation_text=f"Entry: {entry_price:.4f}",
            annotation_position="right",
            row=1, col=1
        )

        # Ligne de prix actuel
        fig.add_hline(
            y=current_price,
            line_dash="dot",
            line_color="white",
            annotation_text=f"Current: {current_price:.4f}",
            annotation_position="right",
            row=1, col=1
        )

    # 5. Affichage des trades récents
    if recent_trades:
        buy_trades = [t for t in recent_trades if t['side'] == 'BUY']
        sell_trades = [t for t in recent_trades if t['side'] == 'SELL']

        if buy_trades:
            buy_dates = [datetime.fromisoformat(t['ts']) for t in buy_trades]
            buy_prices = [t['price'] for t in buy_trades]

            fig.add_trace(
                go.Scatter(
                    x=buy_dates,
                    y=buy_prices,
                    mode='markers',
                    name='BUY',
                    marker=dict(
                        symbol='triangle-up',
                        size=15,
                        color='#00E676',
                        line=dict(width=2, color='white')
                    )
                ),
                row=1, col=1
            )

        if sell_trades:
            sell_dates = [datetime.fromisoformat(t['ts']) for t in sell_trades]
            sell_prices = [t['price'] for t in sell_trades]

            fig.add_trace(
                go.Scatter(
                    x=sell_dates,
                    y=sell_prices,
                    mode='markers',
                    name='SELL',
                    marker=dict(
                        symbol='triangle-down',
                        size=15,
                        color='#FF5252',
                        line=dict(width=2, color='white')
                    )
                ),
                row=1, col=1
            )

    # 6. RSI
    fig.add_trace(
        go.Scatter(
            x=df['datetime'],
            y=rsi,
            mode='lines',
            name='RSI',
            line=dict(color='#9C27B0', width=2)
        ),
        row=2, col=1
    )

    # Zones RSI
    fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5, row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5, row=2, col=1)
    fig.add_hline(y=55, line_dash="dot", line_color="orange", opacity=0.3, row=2, col=1)
    fig.add_hline(y=35, line_dash="dot", line_color="cyan", opacity=0.3, row=2, col=1)

    # 7. ADX et DMI
    fig.add_trace(
        go.Scatter(
            x=df['datetime'],
            y=adx,
            mode='lines',
            name='ADX',
            line=dict(color='#FFC107', width=2)
        ),
        row=3, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=df['datetime'],
            y=plus_di,
            mode='lines',
            name='DI+',
            line=dict(color='#4CAF50', width=1.5)
        ),
        row=3, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=df['datetime'],
            y=minus_di,
            mode='lines',
            name='DI-',
            line=dict(color='#F44336', width=1.5)
        ),
        row=3, col=1
    )

    # Seuil ADX
    fig.add_hline(y=25, line_dash="dash", line_color="white", opacity=0.3, row=3, col=1)

    # 8. P&L Non Réalisé (si position ouverte)
    if bot_position and bot_position.get('side') == 'LONG':
        qty = bot_position.get('qty', 0)
        entry_price = bot_position.get('entry_price', 0)

        # Calculer P&L pour chaque bougie
        pnl_unrealized = [(close - entry_price) * qty for close in df['close']]

        fig.add_trace(
            go.Scatter(
                x=df['datetime'],
                y=pnl_unrealized,
                mode='lines',
                name='P&L Non Réalisé',
                line=dict(color='#00BCD4', width=2),
                fill='tozeroy',
                fillcolor='rgba(0, 188, 212, 0.2)'
            ),
            row=4, col=1
        )

        # Ligne zéro
        fig.add_hline(y=0, line_dash="solid", line_color="white", opacity=0.5, row=4, col=1)
    else:
        # Pas de position, afficher ligne plate à zéro
        fig.add_trace(
            go.Scatter(
                x=df['datetime'],
                y=[0] * len(df),
                mode='lines',
                name='Pas de Position',
                line=dict(color='gray', width=1),
                fill='tozeroy',
                fillcolor='rgba(128, 128, 128, 0.1)'
            ),
            row=4, col=1
        )

    # Mise en forme
    fig.update_layout(
        height=1000,
        template='plotly_dark',
        hovermode='x unified',
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    # Axes Y
    fig.update_yaxes(title_text="Prix (USDT)", row=1, col=1)
    fig.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1)
    fig.update_yaxes(title_text="ADX/DMI", range=[0, 100], row=3, col=1)
    fig.update_yaxes(title_text="P&L (USDT)", row=4, col=1)

    # Axe X
    fig.update_xaxes(title_text="Temps", row=4, col=1)

    return fig


def get_bot_realtime_data(
    symbol: str,
    interval: str,
    api_key: str,
    api_secret: str,
    testnet: bool = True
) -> Dict:
    """
    Récupère toutes les données nécessaires pour afficher le graphique temps réel d'un bot.

    Returns:
        Dict contenant:
        - candles: Liste des bougies OHLCV
        - position: Position actuelle du bot (ou None)
        - trades: Trades récents du bot
    """
    # Récupération des klines
    candles = asyncio.run(fetch_realtime_klines(
        symbol=symbol,
        interval=interval,
        lookback_candles=200,
        api_key=api_key,
        api_secret=api_secret,
        testnet=testnet
    ))

    # Récupération de la position actuelle
    positions = fetch_positions()
    bot_position = None
    for pos in positions:
        if pos['symbol'] == symbol:
            bot_position = pos
            break

    # Récupération des trades récents (dernières 24h)
    all_trades = fetch_trades(symbol=symbol, limit=100)
    recent_trades = [
        t for t in all_trades
        if (datetime.now() - datetime.fromisoformat(t['ts'])) < timedelta(hours=24)
    ]

    return {
        'candles': candles,
        'position': bot_position,
        'trades': recent_trades
    }
