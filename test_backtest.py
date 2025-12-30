"""
Script de test pour le module de backtesting
"""

import asyncio
from datetime import datetime, timedelta
from backtest import run_backtest_async
from backtest_viz import create_backtest_chart, create_statistics_summary
import os


async def test_backtest():
    """Test du backtest avec des données réelles"""
    print("🧪 Test du système de backtesting...")
    print("-" * 60)

    # Configuration
    symbol = "BTCUSDT"
    interval = "1h"
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)  # 7 jours de données
    allocation_pct = 10.0
    initial_capital = 10000.0

    # Get API credentials
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")

    if not api_key or not api_secret:
        print("❌ BINANCE_API_KEY ou BINANCE_API_SECRET non défini")
        print("   Utilisez un fichier .env ou définissez les variables d'environnement")
        return

    print(f"📊 Symbole: {symbol}")
    print(f"⏰ Intervalle: {interval}")
    print(f"📅 Période: {start_date.strftime('%Y-%m-%d')} → {end_date.strftime('%Y-%m-%d')}")
    print(f"💰 Capital initial: ${initial_capital:.2f}")
    print(f"📊 Allocation par trade: {allocation_pct}% du capital disponible")
    print("-" * 60)

    try:
        # Run backtest
        print("\n⏳ Téléchargement des données historiques...")
        results = await run_backtest_async(
            symbol=symbol,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
            allocation_pct=allocation_pct,
            initial_capital=initial_capital,
            testnet=True,
            api_key=api_key,
            api_secret=api_secret
        )

        print("✅ Backtest terminé avec succès!\n")

        # Display statistics
        stats = results['statistics']
        print("=" * 60)
        print("📊 RÉSULTATS DU BACKTEST")
        print("=" * 60)
        print(f"\n📈 STATISTIQUES DE TRADING:")
        print(f"   Total d'ordres: {stats['total_trades']}")
        print(f"   Ordres d'achat: {stats['buy_orders']}")
        print(f"   Ordres de vente: {stats['sell_orders']}")
        print(f"   Trades gagnants: {stats['winning_trades']}")
        print(f"   Trades perdants: {stats['losing_trades']}")
        print(f"   Win rate: {stats['win_rate']:.2f}%")

        print(f"\n💰 PROFIT & LOSS:")
        print(f"   P&L total: ${stats['total_pnl']:.2f}")
        print(f"   Rendement: {stats['return_pct']:.2f}%")
        print(f"   Capital initial: ${initial_capital:.2f}")
        print(f"   Capital final: ${stats['final_capital']:.2f}")
        print(f"   Gain moyen: ${stats['avg_win']:.2f}")
        print(f"   Perte moyenne: ${stats['avg_loss']:.2f}")
        print(f"   Plus grand gain: ${stats['largest_win']:.2f}")
        print(f"   Plus grande perte: ${stats['largest_loss']:.2f}")

        print(f"\n⚠️ GESTION DU RISQUE:")
        print(f"   Max drawdown: ${stats['max_drawdown']:.2f}")
        print(f"   Max drawdown %: {stats['max_drawdown_pct']:.2f}%")
        print(f"   Profit factor: {stats['profit_factor']:.2f}")

        print(f"\n⏱️ TEMPS DE DÉTENTION:")
        print(f"   Temps moyen: {stats['avg_hold_time_hours']:.2f} heures")

        # Display trades summary
        print(f"\n📝 DÉTAIL DES TRADES:")
        trades = results['trades']
        if trades:
            for i, trade in enumerate(trades[:10], 1):  # Show first 10 trades
                print(f"\n   Trade #{i}:")
                print(f"      Type: {trade['side']}")
                print(f"      Prix: ${trade['price']:.2f}")
                print(f"      Quantité: {trade['qty']:.6f}")
                print(f"      Montant: ${trade['quote_qty']:.2f}")
                print(f"      Date: {trade['datetime']}")
                if trade['side'] == 'SELL' and 'pnl' in trade:
                    print(f"      P&L: ${trade['pnl']:.2f} ({trade['pnl_pct']:.2f}%)")

            if len(trades) > 10:
                print(f"\n   ... et {len(trades) - 10} autres trades")
        else:
            print("   Aucun trade exécuté")

        # Display pivots summary
        pivots = results['pivots']
        print(f"\n🎯 PIVOTS DÉTECTÉS:")
        print(f"   Total de pivots: {len(pivots)}")
        pivot_highs = [p for p in pivots if p['type'] == 'HIGH']
        pivot_lows = [p for p in pivots if p['type'] == 'LOW']
        print(f"   Pivots hauts: {len(pivot_highs)}")
        print(f"   Pivots bas: {len(pivot_lows)}")

        print("\n" + "=" * 60)

        # Evaluation
        print("\n💡 ÉVALUATION DE LA STRATÉGIE:")
        if stats['total_trades'] == 0:
            print("   ⚠️ Aucun trade exécuté - La stratégie n'a généré aucun signal")
        else:
            if stats['return_pct'] > 0:
                print(f"   ✅ Stratégie RENTABLE avec {stats['return_pct']:.2f}% de rendement")
            else:
                print(f"   ❌ Stratégie NON RENTABLE ({stats['return_pct']:.2f}% de perte)")

            if stats['win_rate'] >= 50:
                print(f"   ✅ Bon taux de réussite ({stats['win_rate']:.2f}%)")
            else:
                print(f"   ⚠️ Taux de réussite faible ({stats['win_rate']:.2f}%)")

            if stats['profit_factor'] >= 1:
                print(f"   ✅ Profit factor positif ({stats['profit_factor']:.2f})")
            else:
                print(f"   ❌ Profit factor négatif ({stats['profit_factor']:.2f})")

            if stats['max_drawdown_pct'] <= 10:
                print(f"   ✅ Drawdown bien contrôlé ({stats['max_drawdown_pct']:.2f}%)")
            elif stats['max_drawdown_pct'] <= 20:
                print(f"   ⚠️ Drawdown modéré ({stats['max_drawdown_pct']:.2f}%)")
            else:
                print(f"   ❌ Drawdown élevé ({stats['max_drawdown_pct']:.2f}%) - Risque important!")

        print("\n✅ Test terminé avec succès!")

    except Exception as e:
        print(f"\n❌ Erreur durant le test: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_backtest())
