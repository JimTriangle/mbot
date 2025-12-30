"""
Test unitaire pour la méthode update() de ThreeSwingsStrategy
"""

from bot_core import ThreeSwingsStrategy


def test_update_method():
    """Test que la méthode update() existe et fonctionne correctement"""
    print("🧪 Test de la méthode update() de ThreeSwingsStrategy...")

    # Créer une instance de stratégie
    strategy = ThreeSwingsStrategy(
        left=3,
        right=3,
        max_candles=200,
        timeframe="1m",
        min_pivot_distance=20
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

    # Vérifier que les niveaux de breakout ont été calculés
    print(f"   Structure: {strategy.current_structure}")
    print(f"   Niveau BUY: {strategy.buy_level}")
    print(f"   Niveau SELL: {strategy.sell_level}")

    print("\n✅ Tous les tests sont passés!")
    return True


def test_check_breakout():
    """Test que check_breakout() a la bonne signature"""
    print("\n🧪 Test de la méthode check_breakout()...")

    strategy = ThreeSwingsStrategy()

    # Ajouter quelques bougies
    for i in range(10):
        candle = {
            'timestamp': 1609459200000 + i * 60000,
            'open': 29000.0 + i * 10,
            'high': 29100.0 + i * 10,
            'low': 28900.0 + i * 10,
            'close': 29050.0 + i * 10,
            'volume': 100.0
        }
        strategy.update(candle)

    # Définir manuellement un niveau pour tester
    strategy.buy_level = 29100.0

    # Tester check_breakout avec un prix qui ne casse pas
    signal = strategy.check_breakout(29000.0)
    if signal is not None:
        print(f"❌ Erreur: signal={signal} au lieu de None")
        return False
    print("✅ check_breakout() retourne None quand pas de breakout")

    # Tester check_breakout avec un prix qui casse
    signal = strategy.check_breakout(29200.0)
    if signal != "BUY":
        print(f"❌ Erreur: signal={signal} au lieu de 'BUY'")
        return False
    print("✅ check_breakout() retourne 'BUY' lors d'un breakout haussier")

    # Tester avec timestamp (pour compatibilité avec backtest)
    strategy.sell_level = 28800.0
    signal = strategy.check_breakout(28700.0, timestamp=1609459200000)
    if signal != "SELL":
        print(f"❌ Erreur: signal={signal} au lieu de 'SELL'")
        return False
    print("✅ check_breakout() accepte le paramètre timestamp")

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
