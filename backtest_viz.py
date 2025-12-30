"""
Module de visualisation pour les résultats de backtesting et de production
Utilise Plotly pour créer des graphiques interactifs unifiés
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime


def create_backtest_chart(results: Dict) -> go.Figure:
    """
    Create comprehensive backtest visualization

    Args:
        results: Backtest results dictionary from BacktestEngine

    Returns:
        Plotly figure with candlestick chart, trades, pivots, and indicators
    """
    price_data = results['price_data']
    trades = results['trades']
    pivots = results['pivots']

    if not price_data:
        # Return empty figure
        fig = go.Figure()
        fig.add_annotation(
            text="Aucune donnée à afficher",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=20)
        )
        return fig

    # Convert price data to DataFrame
    df = pd.DataFrame(price_data)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

    # Create figure with subplots
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
        subplot_titles=('Prix et Trades', 'P&L Cumulé')
    )

    # Add candlestick chart
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
        row=1,
        col=1
    )

    # Add buy signals
    buy_trades = [t for t in trades if t['side'] == 'BUY']
    if buy_trades:
        buy_df = pd.DataFrame(buy_trades)
        buy_df['datetime'] = pd.to_datetime(buy_df['timestamp'], unit='ms')

        fig.add_trace(
            go.Scatter(
                x=buy_df['datetime'],
                y=buy_df['price'],
                mode='markers',
                name='Achat',
                marker=dict(
                    symbol='triangle-up',
                    size=15,
                    color='#00ff00',
                    line=dict(color='#006400', width=2)
                ),
                text=[f"Achat<br>Prix: ${p:.2f}<br>Qty: {q:.4f}" for p, q in zip(buy_df['price'], buy_df['qty'])],
                hovertemplate='<b>%{text}</b><br>%{x}<extra></extra>'
            ),
            row=1,
            col=1
        )

    # Add sell signals
    sell_trades = [t for t in trades if t['side'] == 'SELL']
    if sell_trades:
        sell_df = pd.DataFrame(sell_trades)
        sell_df['datetime'] = pd.to_datetime(sell_df['timestamp'], unit='ms')

        # Color based on profit/loss
        colors = ['#ff0000' if pnl < 0 else '#00ff00' for pnl in sell_df['pnl']]

        fig.add_trace(
            go.Scatter(
                x=sell_df['datetime'],
                y=sell_df['price'],
                mode='markers',
                name='Vente',
                marker=dict(
                    symbol='triangle-down',
                    size=15,
                    color=colors,
                    line=dict(color='#000000', width=2)
                ),
                text=[
                    f"Vente<br>Prix: ${p:.2f}<br>Qty: {q:.4f}<br>P&L: ${pnl:.2f} ({pnl_pct:.2f}%)"
                    for p, q, pnl, pnl_pct in zip(
                        sell_df['price'],
                        sell_df['qty'],
                        sell_df['pnl'],
                        sell_df['pnl_pct']
                    )
                ],
                hovertemplate='<b>%{text}</b><br>%{x}<extra></extra>'
            ),
            row=1,
            col=1
        )

    # Add pivot highs
    pivot_highs = [p for p in pivots if p['type'] == 'HIGH']
    if pivot_highs:
        pivot_high_df = pd.DataFrame(pivot_highs)
        pivot_high_df['datetime'] = pd.to_datetime(pivot_high_df['timestamp'], unit='ms')

        fig.add_trace(
            go.Scatter(
                x=pivot_high_df['datetime'],
                y=pivot_high_df['price'],
                mode='markers',
                name='Pivot Haut',
                marker=dict(
                    symbol='star',
                    size=10,
                    color='#ff69b4',
                    line=dict(color='#ff1493', width=1)
                ),
                text=[f"Pivot Haut<br>Prix: ${p:.2f}" for p in pivot_high_df['price']],
                hovertemplate='<b>%{text}</b><br>%{x}<extra></extra>'
            ),
            row=1,
            col=1
        )

    # Add pivot lows
    pivot_lows = [p for p in pivots if p['type'] == 'LOW']
    if pivot_lows:
        pivot_low_df = pd.DataFrame(pivot_lows)
        pivot_low_df['datetime'] = pd.to_datetime(pivot_low_df['timestamp'], unit='ms')

        fig.add_trace(
            go.Scatter(
                x=pivot_low_df['datetime'],
                y=pivot_low_df['price'],
                mode='markers',
                name='Pivot Bas',
                marker=dict(
                    symbol='star',
                    size=10,
                    color='#87ceeb',
                    line=dict(color='#4682b4', width=1)
                ),
                text=[f"Pivot Bas<br>Prix: ${p:.2f}" for p in pivot_low_df['price']],
                hovertemplate='<b>%{text}</b><br>%{x}<extra></extra>'
            ),
            row=1,
            col=1
        )

    # Add cumulative P&L chart
    if sell_trades:
        sell_df = pd.DataFrame(sell_trades)
        sell_df['datetime'] = pd.to_datetime(sell_df['timestamp'], unit='ms')
        sell_df['cumulative_pnl'] = sell_df['pnl'].cumsum()

        # Color based on positive/negative
        colors_pnl = ['#ff0000' if pnl < 0 else '#00ff00' for pnl in sell_df['cumulative_pnl']]

        fig.add_trace(
            go.Scatter(
                x=sell_df['datetime'],
                y=sell_df['cumulative_pnl'],
                mode='lines+markers',
                name='P&L Cumulé',
                line=dict(color='#2196F3', width=2),
                marker=dict(size=6, color=colors_pnl),
                fill='tozeroy',
                fillcolor='rgba(33, 150, 243, 0.1)',
                text=[f"P&L: ${pnl:.2f}" for pnl in sell_df['cumulative_pnl']],
                hovertemplate='<b>%{text}</b><br>%{x}<extra></extra>'
            ),
            row=2,
            col=1
        )

        # Add zero line
        fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)

    # Update layout
    fig.update_layout(
        title='Résultats du Backtesting - Stratégie 3 Swings',
        xaxis_title='Date',
        yaxis_title='Prix ($)',
        xaxis2_title='Date',
        yaxis2_title='P&L Cumulé ($)',
        hovermode='x unified',
        height=800,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        template='plotly_dark',
        # Preserve UI state during interactions
        uirevision='constant'
    )

    # Calculate reasonable Y-axis range to handle outliers
    # This prevents a single extreme candle from making the rest of the chart unreadable
    all_highs = df['high'].values
    all_lows = df['low'].values

    # Use percentiles to identify reasonable price range
    # This excludes extreme outliers from the initial view
    p1 = np.percentile(all_highs, 1)   # 1st percentile
    p99 = np.percentile(all_highs, 99)  # 99th percentile
    l1 = np.percentile(all_lows, 1)
    l99 = np.percentile(all_lows, 99)

    # Determine if there are extreme outliers (values > 3x the 99th percentile range)
    price_range = p99 - l1
    max_high = np.max(all_highs)
    has_extreme_outlier = max_high > (p99 + 2 * price_range)

    if has_extreme_outlier:
        # If we have extreme outliers, set a fixed range based on percentiles
        # Add 5% margin for better visibility
        margin = price_range * 0.05
        y_min = l1 - margin
        y_max = p99 + margin

        fig.update_yaxes(
            range=[y_min, y_max],
            fixedrange=False,  # Allow manual zoom
            row=1,
            col=1
        )

        # Add annotation to inform user about outliers
        fig.add_annotation(
            text="⚠️ Valeurs extrêmes détectées - Échelle ajustée. Zoomez ou utilisez 'Autoscale' pour voir toutes les données",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.98,
            xanchor="center",
            yanchor="top",
            showarrow=False,
            font=dict(size=10, color="orange"),
            bgcolor="rgba(0,0,0,0.6)",
            bordercolor="orange",
            borderwidth=1,
            row=1,
            col=1
        )
    else:
        # No extreme outliers, use auto-ranging
        fig.update_yaxes(
            autorange=True,
            fixedrange=False,
            row=1,
            col=1
        )

    # Configure X-axis
    fig.update_xaxes(
        rangeslider_visible=False,
        row=1,
        col=1
    )

    return fig


def create_statistics_summary(stats: Dict) -> str:
    """
    Create formatted statistics summary

    Args:
        stats: Statistics dictionary from BacktestEngine

    Returns:
        Formatted string with statistics (plain text for Streamlit)
    """
    if stats['total_trades'] == 0:
        return "Aucun trade exécuté durant le backtest."

    # Build summary as plain text for better compatibility
    summary = f"""
### Résumé des Performances

#### Statistiques de Trading
- **Total d'ordres:** {stats['total_trades']}
- **Ordres d'achat:** {stats['buy_orders']}
- **Ordres de vente:** {stats['sell_orders']}
- **Trades gagnants:** {stats['winning_trades']} :green_circle:
- **Trades perdants:** {stats['losing_trades']} :red_circle:
- **Win Rate:** {stats['win_rate']:.2f}% {'✅' if stats['win_rate'] >= 50 else '⚠️'}

#### Profit & Loss
- **P&L Total:** ${stats['total_pnl']:.2f} {'📈' if stats['total_pnl'] >= 0 else '📉'}
- **Rendement:** {stats['return_pct']:.2f}% {'✅' if stats['return_pct'] >= 0 else '❌'}
- **Capital Final:** ${stats['final_capital']:.2f}
- **Gain Moyen:** ${stats['avg_win']:.2f}
- **Perte Moyenne:** ${stats['avg_loss']:.2f}
- **Plus Grand Gain:** ${stats['largest_win']:.2f}
- **Plus Grande Perte:** ${stats['largest_loss']:.2f}

#### Gestion du Risque
- **Max Drawdown:** ${stats['max_drawdown']:.2f}
- **Max Drawdown %:** {stats['max_drawdown_pct']:.2f}%
- **Profit Factor:** {stats['profit_factor']:.2f} {'✅' if stats['profit_factor'] >= 1 else '❌'}

#### Temps de Détention
- **Temps moyen:** {stats['avg_hold_time_hours']:.2f} heures

---

**Interprétation:**
"""

    # Add interpretation based on metrics
    if stats['win_rate'] >= 60:
        summary += "\n- ✅ Excellent taux de réussite (≥60%)"
    elif stats['win_rate'] >= 50:
        summary += "\n- ✔️ Bon taux de réussite (≥50%)"
    else:
        summary += "\n- ⚠️ Taux de réussite faible (<50%) - Optimisation nécessaire"

    if stats['profit_factor'] >= 2:
        summary += "\n- ✅ Excellent profit factor (≥2) - Gains >> Pertes"
    elif stats['profit_factor'] >= 1:
        summary += "\n- ✔️ Profit factor positif (≥1) - Stratégie rentable"
    else:
        summary += "\n- ❌ Profit factor négatif (<1) - Stratégie non rentable"

    if stats['max_drawdown_pct'] <= 10:
        summary += "\n- ✅ Drawdown contrôlé (≤10%)"
    elif stats['max_drawdown_pct'] <= 20:
        summary += "\n- ⚠️ Drawdown modéré (10-20%)"
    else:
        summary += "\n- ❌ Drawdown élevé (>20%) - Risque important"

    if stats['return_pct'] > 0:
        summary += f"\n- ✅ Stratégie profitable avec {stats['return_pct']:.2f}% de rendement"
    else:
        summary += f"\n- ❌ Stratégie non profitable ({stats['return_pct']:.2f}%)"

    return summary


def create_trades_dataframe(trades: List[Dict]) -> pd.DataFrame:
    """
    Create formatted DataFrame for trades display

    Args:
        trades: List of trade dictionaries

    Returns:
        Pandas DataFrame with formatted trades
    """
    if not trades:
        return pd.DataFrame()

    df = pd.DataFrame(trades)

    # Select base columns (always present)
    columns = ['datetime', 'side', 'price', 'qty', 'quote_qty']

    # For SELL trades, add PnL-related columns
    # For BUY trades, these will be filled with '-' or empty values
    if 'pnl' in df.columns:
        columns.extend(['pnl', 'pnl_pct', 'entry_price', 'hold_time_hours'])

    # Filter to available columns and create a copy
    available_columns = [col for col in columns if col in df.columns]
    df = df[available_columns].copy()

    # Fill NaN values for BUY trades with appropriate markers
    if 'pnl' in df.columns:
        df['pnl'] = df['pnl'].fillna(0)
    if 'pnl_pct' in df.columns:
        df['pnl_pct'] = df['pnl_pct'].fillna(0)
    if 'entry_price' in df.columns:
        df['entry_price'] = df['entry_price'].fillna(0)
    if 'hold_time_hours' in df.columns:
        df['hold_time_hours'] = df['hold_time_hours'].fillna(0)

    # Rename columns in French
    rename_map = {
        'datetime': 'Date/Heure',
        'side': 'Type',
        'price': 'Prix ($)',
        'qty': 'Quantité',
        'quote_qty': 'Montant ($)',
        'pnl': 'P&L ($)',
        'pnl_pct': 'P&L (%)',
        'entry_price': "Prix d'Entrée ($)",
        'hold_time_hours': 'Détention (h)'
    }

    df.rename(columns=rename_map, inplace=True)

    # Format numeric columns
    if 'Prix ($)' in df.columns:
        df['Prix ($)'] = df['Prix ($)'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "-")

    if 'Quantité' in df.columns:
        df['Quantité'] = df['Quantité'].apply(lambda x: f"{x:.6f}" if pd.notna(x) else "-")

    if 'Montant ($)' in df.columns:
        df['Montant ($)'] = df['Montant ($)'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "-")

    # For P&L columns, show '-' for BUY trades (where values are 0)
    if 'P&L ($)' in df.columns:
        pnl_col = 'P&L ($)'
        df[pnl_col] = df.apply(
            lambda row: "-" if row['Type'] == 'BUY' else f"{float(row[pnl_col]):.2f}",
            axis=1
        )

    if 'P&L (%)' in df.columns:
        pnl_pct_col = 'P&L (%)'
        df[pnl_pct_col] = df.apply(
            lambda row: "-" if row['Type'] == 'BUY' else f"{float(row[pnl_pct_col]):.2f}",
            axis=1
        )

    if "Prix d'Entrée ($)" in df.columns:
        entry_col = "Prix d'Entrée ($)"
        df[entry_col] = df.apply(
            lambda row: "-" if row['Type'] == 'BUY' else f"{float(row[entry_col]):.2f}",
            axis=1
        )

    if 'Détention (h)' in df.columns:
        hold_col = 'Détention (h)'
        df[hold_col] = df.apply(
            lambda row: "-" if row['Type'] == 'BUY' else f"{float(row[hold_col]):.2f}",
            axis=1
        )

    return df


def create_production_chart(
    price_data: List[Dict],
    trades: List[Dict],
    title: str = "Graphique de Production - Trading en Direct"
) -> go.Figure:
    """
    Create production trading visualization with the same format as backtest

    Args:
        price_data: List of candles with OHLCV data
        trades: List of production trades from database
        title: Chart title

    Returns:
        Plotly figure with candlestick chart and trades
    """
    if not price_data:
        # Return empty figure
        fig = go.Figure()
        fig.add_annotation(
            text="Aucune donnée de prix disponible",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=20)
        )
        return fig

    # Convert price data to DataFrame
    df = pd.DataFrame(price_data)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

    # Create figure with subplots
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
        subplot_titles=('Prix et Trades (Production)', 'P&L Cumulé (Réalisé)')
    )

    # Add candlestick chart
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
        row=1,
        col=1
    )

    # Process trades
    if trades:
        # Convert trades to DataFrame
        trades_df = pd.DataFrame(trades)

        # Convert timestamp
        if 'ts' in trades_df.columns:
            trades_df['datetime'] = pd.to_datetime(trades_df['ts'])
        elif 'timestamp' in trades_df.columns:
            trades_df['datetime'] = pd.to_datetime(trades_df['timestamp'], unit='ms')

        # Add buy signals
        buy_trades = trades_df[trades_df['side'] == 'BUY']
        if not buy_trades.empty:
            fig.add_trace(
                go.Scatter(
                    x=buy_trades['datetime'],
                    y=buy_trades['price'],
                    mode='markers',
                    name='Achat (Production)',
                    marker=dict(
                        symbol='triangle-up',
                        size=15,
                        color='#00ff00',
                        line=dict(color='#006400', width=2)
                    ),
                    text=[f"Achat RÉEL<br>Prix: ${p:.2f}<br>Qty: {q:.6f}"
                          for p, q in zip(buy_trades['price'], buy_trades['qty'])],
                    hovertemplate='<b>%{text}</b><br>%{x}<extra></extra>'
                ),
                row=1,
                col=1
            )

        # Add sell signals
        sell_trades = trades_df[trades_df['side'] == 'SELL']
        if not sell_trades.empty:
            # Color based on profit/loss
            colors = ['#ff0000' if (pnl and pnl < 0) else '#00ff00'
                     for pnl in sell_trades['pnl'].fillna(0)]

            fig.add_trace(
                go.Scatter(
                    x=sell_trades['datetime'],
                    y=sell_trades['price'],
                    mode='markers',
                    name='Vente (Production)',
                    marker=dict(
                        symbol='triangle-down',
                        size=15,
                        color=colors,
                        line=dict(color='#000000', width=2)
                    ),
                    text=[
                        f"Vente RÉELLE<br>Prix: ${p:.2f}<br>Qty: {q:.6f}<br>P&L: ${pnl:.2f}"
                        for p, q, pnl in zip(
                            sell_trades['price'],
                            sell_trades['qty'],
                            sell_trades['pnl'].fillna(0)
                        )
                    ],
                    hovertemplate='<b>%{text}</b><br>%{x}<extra></extra>'
                ),
                row=1,
                col=1
            )

        # Add cumulative P&L chart (only for SELL trades with PnL)
        sell_with_pnl = sell_trades.dropna(subset=['pnl'])
        if not sell_with_pnl.empty:
            sell_with_pnl = sell_with_pnl.sort_values('datetime')
            sell_with_pnl['cumulative_pnl'] = sell_with_pnl['pnl'].cumsum()

            # Color based on positive/negative
            colors_pnl = ['#ff0000' if pnl < 0 else '#00ff00'
                         for pnl in sell_with_pnl['cumulative_pnl']]

            fig.add_trace(
                go.Scatter(
                    x=sell_with_pnl['datetime'],
                    y=sell_with_pnl['cumulative_pnl'],
                    mode='lines+markers',
                    name='P&L Cumulé (Production)',
                    line=dict(color='#2196F3', width=2),
                    marker=dict(size=6, color=colors_pnl),
                    fill='tozeroy',
                    fillcolor='rgba(33, 150, 243, 0.1)',
                    text=[f"P&L: ${pnl:.2f}" for pnl in sell_with_pnl['cumulative_pnl']],
                    hovertemplate='<b>%{text}</b><br>%{x}<extra></extra>'
                ),
                row=2,
                col=1
            )

            # Add zero line
            fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)

    # Update layout
    fig.update_layout(
        title=title,
        xaxis_title='Date',
        yaxis_title='Prix ($)',
        xaxis2_title='Date',
        yaxis2_title='P&L Cumulé ($)',
        hovermode='x unified',
        height=800,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        template='plotly_dark',
        uirevision='constant'
    )

    # Calculate reasonable Y-axis range
    all_highs = df['high'].values
    all_lows = df['low'].values

    p1 = np.percentile(all_highs, 1)
    p99 = np.percentile(all_highs, 99)
    l1 = np.percentile(all_lows, 1)

    price_range = p99 - l1
    max_high = np.max(all_highs)
    has_extreme_outlier = max_high > (p99 + 2 * price_range)

    if has_extreme_outlier:
        margin = price_range * 0.05
        y_min = l1 - margin
        y_max = p99 + margin

        fig.update_yaxes(
            range=[y_min, y_max],
            fixedrange=False,
            row=1,
            col=1
        )

        fig.add_annotation(
            text="⚠️ Valeurs extrêmes détectées - Échelle ajustée. Zoomez pour voir toutes les données",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.98,
            xanchor="center",
            yanchor="top",
            showarrow=False,
            font=dict(size=10, color="orange"),
            bgcolor="rgba(0,0,0,0.6)",
            bordercolor="orange",
            borderwidth=1,
            row=1,
            col=1
        )
    else:
        fig.update_yaxes(
            autorange=True,
            fixedrange=False,
            row=1,
            col=1
        )

    fig.update_xaxes(
        rangeslider_visible=False,
        row=1,
        col=1
    )

    return fig
