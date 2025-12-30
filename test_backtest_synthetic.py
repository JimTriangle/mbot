"""
Test du backtest avec des données synthétiques (sans API Binance)
"""

from backtest import BacktestEngine
from datetime import datetime


def generate_synthetic_candles(count=100, start_price=29000.0):
    """Génère des bougies synthétiques pour le test"""
    candles = []
    timestamp = 1609459200000  # 2021-01-01 00:00:00

    for i in range(count):
        # Créer un pattern en zigzag pour générer des pivots
        if i % 10 < 5:
            # Tendance haussière
            open_price = start_price + i * 10
            close_price = open_price + 50
            high = close_price + 20
            low = open_price - 10
        else:
            # Tendance baissière
            open_price = start_price + i * 10
            close_price = open_price - 50
            high = open_price + 10
            low = close_price - 20

        candle = {
            'timestamp': timestamp + i * 60000,  # 1 minute par bougie
            'open': open_price,
            'high': high,
            'low': low,
            'close': close_price,
            'volume': 100.0 + i
        }
        candles.append(candle)

    return candles


def test_backtest_synthetic():
    """Test du backtest avec des données synthétiques"""
    print("🧪 Test du backtest avec données synthétiques...")
    print("-" * 60)

    # Créer le moteur de backtest
    engine = BacktestEngine(
        symbol="BTCUSDT",
        interval="1m",
        allocation_pct=10.0,
        testnet=True
    )

    print("✅ BacktestEngine créé")

    # Générer des données synthétiques
    candles = generate_synthetic_candles(count=150)
    print(f"✅ {len(candles)} bougies synthétiques générées")

    # Exécuter le backtest
    try:
        print("\n⏳ Exécution du backtest...")
        results = engine.run_backtest(candles, initial_capital=10000.0)
        print("✅ Backtest exécuté sans erreur!")

    except AttributeError as e:
        print(f"❌ Erreur AttributeError: {e}")
        print("   Cela indique probablement que la méthode update() n'existe pas")
        return False

    except Exception as e:
        print(f"❌ Erreur lors du backtest: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Afficher les résultats
    print("\n" + "=" * 60)
    print("📊 RÉSULTATS DU BACKTEST")
    print("=" * 60)

    stats = results['statistics']
    print(f"\n📈 STATISTIQUES:")
    print(f"   Total d'ordres: {stats['total_trades']}")
    print(f"   Ordres d'achat: {stats['buy_orders']}")
    print(f"   Ordres de vente: {stats['sell_orders']}")
    print(f"   Trades gagnants: {stats['winning_trades']}")
    print(f"   Trades perdants: {stats['losing_trades']}")
    print(f"   Win rate: {stats['win_rate']:.2f}%")

    print(f"\n💰 PERFORMANCE:")
    print(f"   P&L total: ${stats['total_pnl']:.2f}")
    print(f"   Rendement: {stats['return_pct']:.2f}%")
    print(f"   Capital initial: $10,000.00")
    print(f"   Capital final: ${stats['final_capital']:.2f}")

    print(f"\n📊 DONNÉES:")
    print(f"   Bougies traitées: {len(results['price_data'])}")
    print(f"   Pivots détectés: {len(results['pivots'])}")
    print(f"   Niveaux de breakout: {len(results['breakout_levels'])}")

    # Vérifications
    if len(results['price_data']) != len(candles):
        print(f"\n❌ Erreur: {len(results['price_data'])} bougies au lieu de {len(candles)}")
        return False

    print("\n✅ Toutes les vérifications sont passées!")
    return True


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🎯 TEST DU BACKTEST AVEC DONNÉES SYNTHÉTIQUES")
    print("=" * 60 + "\n")

    success = test_backtest_synthetic()

    print("\n" + "=" * 60)
    if success:
        print("🎉 TEST RÉUSSI!")
        print("   La méthode update() fonctionne correctement")
        print("   Le backtest peut traiter les données sans erreur")
    else:
        print("❌ TEST ÉCHOUÉ")
    print("=" * 60 + "\n")

    exit(0 if success else 1)
