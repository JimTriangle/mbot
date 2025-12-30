"""
Module de visualisation pour les résultats de backtesting
Utilise Plotly pour créer des graphiques interactifs
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from typing import Dict, List
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
        template='plotly_dark'
    )

    # Remove rangeslider for cleaner look
    fig.update_xaxes(rangeslider_visible=False, row=1, col=1)

    return fig


def create_statistics_summary(stats: Dict) -> str:
    """
    Create formatted statistics summary

    Args:
        stats: Statistics dictionary from BacktestEngine

    Returns:
        Formatted HTML string with statistics
    """
    if stats['total_trades'] == 0:
        return "<p>Aucun trade exécuté durant le backtest.</p>"

    html = f"""
    <div style='background-color: #1e1e1e; padding: 20px; border-radius: 10px;'>
        <h3 style='color: #2196F3;'>📊 Résumé des Performances</h3>

        <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px;'>
            <div>
                <h4 style='color: #26a69a;'>📈 Statistiques de Trading</h4>
                <ul style='list-style: none; padding: 0;'>
                    <li><strong>Total d'ordres:</strong> {stats['total_trades']}</li>
                    <li><strong>Ordres d'achat:</strong> {stats['buy_orders']}</li>
                    <li><strong>Ordres de vente:</strong> {stats['sell_orders']}</li>
                    <li><strong>Trades gagnants:</strong> <span style='color: #00ff00;'>{stats['winning_trades']}</span></li>
                    <li><strong>Trades perdants:</strong> <span style='color: #ff0000;'>{stats['losing_trades']}</span></li>
                    <li><strong>Win Rate:</strong> <span style='color: {"#00ff00" if stats["win_rate"] >= 50 else "#ff9800"};'>{stats['win_rate']:.2f}%</span></li>
                </ul>
            </div>

            <div>
                <h4 style='color: #2196F3;'>💰 Profit & Loss</h4>
                <ul style='list-style: none; padding: 0;'>
                    <li><strong>P&L Total:</strong> <span style='color: {"#00ff00" if stats["total_pnl"] >= 0 else "#ff0000"};'>${stats['total_pnl']:.2f}</span></li>
                    <li><strong>Rendement:</strong> <span style='color: {"#00ff00" if stats["return_pct"] >= 0 else "#ff0000"};'>{stats['return_pct']:.2f}%</span></li>
                    <li><strong>Capital Final:</strong> ${stats['final_capital']:.2f}</li>
                    <li><strong>Gain Moyen:</strong> <span style='color: #00ff00;'>${stats['avg_win']:.2f}</span></li>
                    <li><strong>Perte Moyenne:</strong> <span style='color: #ff0000;'>${stats['avg_loss']:.2f}</span></li>
                    <li><strong>Plus Grand Gain:</strong> <span style='color: #00ff00;'>${stats['largest_win']:.2f}</span></li>
                    <li><strong>Plus Grande Perte:</strong> <span style='color: #ff0000;'>${stats['largest_loss']:.2f}</span></li>
                </ul>
            </div>

            <div>
                <h4 style='color: #ff9800;'>⚠️ Gestion du Risque</h4>
                <ul style='list-style: none; padding: 0;'>
                    <li><strong>Max Drawdown:</strong> <span style='color: #ff0000;'>${stats['max_drawdown']:.2f}</span></li>
                    <li><strong>Max Drawdown %:</strong> <span style='color: #ff0000;'>{stats['max_drawdown_pct']:.2f}%</span></li>
                    <li><strong>Profit Factor:</strong> <span style='color: {"#00ff00" if stats["profit_factor"] >= 1 else "#ff0000"};'>{stats['profit_factor']:.2f}</span></li>
                </ul>
            </div>

            <div>
                <h4 style='color: #9c27b0;'>⏱️ Temps de Détention</h4>
                <ul style='list-style: none; padding: 0;'>
                    <li><strong>Temps moyen:</strong> {stats['avg_hold_time_hours']:.2f} heures</li>
                </ul>
            </div>
        </div>

        <div style='margin-top: 20px; padding: 15px; background-color: #2a2a2a; border-radius: 5px;'>
            <p style='margin: 0;'><strong>💡 Interprétation:</strong></p>
            <ul style='margin-top: 10px;'>
    """

    # Add interpretation based on metrics
    if stats['win_rate'] >= 60:
        html += "<li>✅ Excellent taux de réussite (≥60%)</li>"
    elif stats['win_rate'] >= 50:
        html += "<li>✔️ Bon taux de réussite (≥50%)</li>"
    else:
        html += "<li>⚠️ Taux de réussite faible (<50%) - Optimisation nécessaire</li>"

    if stats['profit_factor'] >= 2:
        html += "<li>✅ Excellent profit factor (≥2) - Gains >> Pertes</li>"
    elif stats['profit_factor'] >= 1:
        html += "<li>✔️ Profit factor positif (≥1) - Stratégie rentable</li>"
    else:
        html += "<li>❌ Profit factor négatif (<1) - Stratégie non rentable</li>"

    if stats['max_drawdown_pct'] <= 10:
        html += "<li>✅ Drawdown contrôlé (≤10%)</li>"
    elif stats['max_drawdown_pct'] <= 20:
        html += "<li>⚠️ Drawdown modéré (10-20%)</li>"
    else:
        html += "<li>❌ Drawdown élevé (>20%) - Risque important</li>"

    if stats['return_pct'] > 0:
        html += f"<li>✅ Stratégie profitable avec {stats['return_pct']:.2f}% de rendement</li>"
    else:
        html += f"<li>❌ Stratégie non profitable ({stats['return_pct']:.2f}%)</li>"

    html += """
            </ul>
        </div>
    </div>
    """

    return html


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

    # Select and order columns
    columns = ['datetime', 'side', 'price', 'qty', 'quote_qty']

    # Add PnL columns for sell trades
    if 'pnl' in df.columns:
        columns.extend(['pnl', 'pnl_pct'])

    if 'entry_price' in df.columns:
        columns.append('entry_price')

    if 'hold_time_hours' in df.columns:
        columns.append('hold_time_hours')

    # Filter to available columns
    available_columns = [col for col in columns if col in df.columns]
    df = df[available_columns].copy()

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
        df['Prix ($)'] = df['Prix ($)'].apply(lambda x: f"{x:.2f}")

    if 'Quantité' in df.columns:
        df['Quantité'] = df['Quantité'].apply(lambda x: f"{x:.6f}")

    if 'Montant ($)' in df.columns:
        df['Montant ($)'] = df['Montant ($)'].apply(lambda x: f"{x:.2f}")

    if 'P&L ($)' in df.columns:
        df['P&L ($)'] = df['P&L ($)'].apply(lambda x: f"{x:.2f}")

    if 'P&L (%)' in df.columns:
        df['P&L (%)'] = df['P&L (%)'].apply(lambda x: f"{x:.2f}")

    if "Prix d'Entrée ($)" in df.columns:
        df["Prix d'Entrée ($)"] = df["Prix d'Entrée ($)"].apply(lambda x: f"{x:.2f}")

    if 'Détention (h)' in df.columns:
        df['Détention (h)'] = df['Détention (h)'].apply(lambda x: f"{x:.2f}")

    return df
