"""
Test de la validation des données de bougies
"""

from backtest import BacktestEngine


def test_candle_validation():
    """Test la validation des bougies invalides"""
    print("🧪 Test de validation des données de bougies")
    print("-" * 60)

    # Créer une instance du moteur
    engine = BacktestEngine(
        symbol="BTCUSDT",
        interval="1h",
        allocation_pct=10.0
    )

    # Test 1: Bougie valide normale
    valid_candle = {
        'timestamp': 1609459200000,
        'open': 29000.0,
        'high': 29500.0,
        'low': 28800.0,
        'close': 29200.0,
        'volume': 1000.0
    }
    assert engine._is_valid_candle(valid_candle), "❌ Bougie valide rejetée"
    print("✅ Test 1: Bougie valide normale - OK")

    # Test 2: Bougie avec high < low (invalide)
    invalid_candle_1 = {
        'timestamp': 1609459200000,
        'open': 29000.0,
        'high': 28000.0,  # high < low !
        'low': 29000.0,
        'close': 28500.0,
        'volume': 1000.0
    }
    assert not engine._is_valid_candle(invalid_candle_1), "❌ Bougie high<low acceptée"
    print("✅ Test 2: Bougie avec high < low - Rejetée correctement")

    # Test 3: Bougie avec prix négatif (invalide)
    invalid_candle_2 = {
        'timestamp': 1609459200000,
        'open': -29000.0,
        'high': 29500.0,
        'low': 28800.0,
        'close': 29200.0,
        'volume': 1000.0
    }
    assert not engine._is_valid_candle(invalid_candle_2), "❌ Prix négatif accepté"
    print("✅ Test 3: Bougie avec prix négatif - Rejetée correctement")

    # Test 4: Bougie avec range extrême comme celle de l'utilisateur (high: 230k, low: 20k)
    extreme_candle = {
        'timestamp': 1609459200000,
        'open': 25000.0,
        'high': 230000.0,  # 11.5x le low !
        'low': 20000.0,
        'close': 22000.0,
        'volume': 1000.0
    }
    assert not engine._is_valid_candle(extreme_candle), "❌ Bougie extrême acceptée"
    print("✅ Test 4: Bougie avec high/low > 10x (230k/20k) - Rejetée correctement")

    # Test 5: Bougie avec range de prix > 500% du low
    extreme_range = {
        'timestamp': 1609459200000,
        'open': 1000.0,
        'high': 7000.0,  # range = 6000, soit 600% du low (1000)
        'low': 1000.0,
        'close': 1500.0,
        'volume': 1000.0
    }
    assert not engine._is_valid_candle(extreme_range), "❌ Range extrême accepté"
    print("✅ Test 5: Bougie avec range > 500% - Rejetée correctement")

    # Test 6: Bougie avec prix zero
    zero_price = {
        'timestamp': 1609459200000,
        'open': 0.0,
        'high': 100.0,
        'low': 0.0,
        'close': 50.0,
        'volume': 1000.0
    }
    assert not engine._is_valid_candle(zero_price), "❌ Prix zéro accepté"
    print("✅ Test 6: Bougie avec prix = 0 - Rejetée correctement")

    # Test 7: Bougie avec close > high (invalide)
    close_too_high = {
        'timestamp': 1609459200000,
        'open': 29000.0,
        'high': 29500.0,
        'low': 28800.0,
        'close': 30000.0,  # close > high !
        'volume': 1000.0
    }
    assert not engine._is_valid_candle(close_too_high), "❌ Close > high accepté"
    print("✅ Test 7: Bougie avec close > high - Rejetée correctement")

    # Test 8: Bougie normale avec petite variation (valide)
    small_variation = {
        'timestamp': 1609459200000,
        'open': 29000.0,
        'high': 29050.0,
        'low': 28950.0,
        'close': 29020.0,
        'volume': 1000.0
    }
    assert engine._is_valid_candle(small_variation), "❌ Petite variation rejetée"
    print("✅ Test 8: Bougie avec petite variation - OK")

    print("\n" + "=" * 60)
    print("🎉 TOUS LES TESTS SONT PASSÉS !")
    print("=" * 60)
    print("\nLa validation des données fonctionne correctement.")
    print("Les bougies avec des valeurs extrêmes comme 'high: 230k, low: 20k'")
    print("seront maintenant automatiquement filtrées.")


if __name__ == "__main__":
    test_candle_validation()
