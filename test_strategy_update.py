"""
Test unitaire pour la méthode update() de TrendPhaseStrategy
"""

from bot_core import TrendPhaseStrategy


def test_update_method():
    """Test que la méthode update() existe et fonctionne correctement"""
    print("🧪 Test de la méthode update() de TrendPhaseStrategy...")

    # Créer une instance de stratégie
    strategy = TrendPhaseStrategy(
        timeframe="1m"
    )

    print("✅ Stratégie créée")

    # Créer une bougie de test
    candle = {
        'timestamp': 1609459200000,  # 2021-01-01 00:00:00
        'open': 29000.0,
        'high': 29100.0,
        'low': 28900.0,
        'close': 29050.0,
        'volume': 100.0
    }

    print("✅ Bougie de test créée")

    # Tester la méthode update()
    try:
        strategy.update(candle)
        print("✅ Méthode update() exécutée sans erreur")
    except AttributeError as e:
        print(f"❌ Erreur: {e}")
        return False
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")
        return False

    # Vérifier que la bougie a été ajoutée
    if len(strategy.candles) != 1:
        print(f"❌ Erreur: {len(strategy.candles)} bougies au lieu de 1")
        return False

    print(f"✅ Bougie ajoutée correctement ({len(strategy.candles)} bougie)")

    # Vérifier que la bougie ajoutée correspond
    added_candle = list(strategy.candles)[0]
    if added_candle['close'] != candle['close']:
        print(f"❌ Erreur: close={added_candle['close']} au lieu de {candle['close']}")
        return False

    print("✅ Données de la bougie correctes")

    # Ajouter plusieurs bougies pour tester la détection de pivots
    print("\n📊 Ajout de bougies supplémentaires...")
    for i in range(20):
        test_candle = {
            'timestamp': 1609459200000 + (i + 1) * 60000,
            'open': 29000.0 + i * 10,
            'high': 29100.0 + i * 10,
            'low': 28900.0 + i * 10,
            'close': 29050.0 + i * 10,
            'volume': 100.0
        }
        strategy.update(test_candle)

    print(f"✅ {len(strategy.candles)} bougies au total")

    # Vérifier les indicateurs
    status = strategy.get_status()
    print(f"   Structure: {status['structure']}")
    print(f"   Tendance haussière forte: {status['strong_up_trend']}")
    print(f"   Tendance baissière forte: {status['strong_down_trend']}")
    if status['indicators']['rsi']:
        print(f"   RSI: {status['indicators']['rsi']:.2f}")
    if status['indicators']['adx']:
        print(f"   ADX: {status['indicators']['adx']:.2f}")

    print("\n✅ Tous les tests sont passés!")
    return True


def test_check_breakout():
    """Test que check_breakout() a la bonne signature"""
    print("\n🧪 Test de la méthode check_breakout()...")

    strategy = TrendPhaseStrategy()

    # Ajouter beaucoup de bougies pour obtenir des indicateurs valides
    # Simuler une tendance haussière
    print("   Ajout de bougies pour simuler une tendance haussière...")
    for i in range(100):
        candle = {
            'timestamp': 1609459200000 + i * 60000,
            'open': 29000.0 + i * 10,
            'high': 29100.0 + i * 10,
            'low': 28900.0 + i * 10,
            'close': 29050.0 + i * 10,
            'volume': 100.0
        }
        strategy.update(candle)

    # Vérifier que check_breakout fonctionne
    signal = strategy.check_breakout(29500.0)
    print(f"   Signal reçu: {signal}")
    print("✅ check_breakout() fonctionne sans erreur")

    # Tester avec un autre prix
    signal = strategy.check_breakout(29600.0)
    print("✅ check_breakout() fonctionne avec différents prix")

    print("\n✅ Tous les tests check_breakout() sont passés!")
    return True


if __name__ == "__main__":
    success = test_update_method()
    if success:
        success = test_check_breakout()

    if success:
        print("\n" + "=" * 60)
        print("🎉 TOUS LES TESTS SONT PASSÉS!")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ ÉCHEC DE CERTAINS TESTS")
        print("=" * 60)
        exit(1)
