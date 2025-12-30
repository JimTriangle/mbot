#!/usr/bin/env python3
"""
Test de la stratégie TrendPhaseOptimizedStrategy.
Vérifie que les paramètres et la logique correspondent au Pine Script "Phases de Tendance (Optimisé+)".
"""
from strategies import TrendPhaseOptimizedStrategy, create_strategy


def test_parameters():
    """Test des paramètres par défaut"""
    strategy = TrendPhaseOptimizedStrategy(timeframe="1h")

    print("=== Test des paramètres ===")
    assert strategy.ema_short_length == 20, f"EMA courte devrait être 20, reçu: {strategy.ema_short_length}"
    assert strategy.ema_long_length == 50, f"EMA longue devrait être 50, reçu: {strategy.ema_long_length}"
    assert strategy.rsi_length == 14, f"RSI length devrait être 14, reçu: {strategy.rsi_length}"
    assert strategy.adx_length == 14, f"ADX length devrait être 14, reçu: {strategy.adx_length}"
    assert strategy.adx_smoothing == 14, f"ADX smoothing devrait être 14, reçu: {strategy.adx_smoothing}"
    assert strategy.adx_trend_threshold == 25, f"ADX threshold devrait être 25, reçu: {strategy.adx_trend_threshold}"
    assert strategy.rsi_up_threshold == 55, f"RSI up threshold devrait être 55, reçu: {strategy.rsi_up_threshold}"
    assert strategy.rsi_down_threshold == 30, f"RSI down threshold devrait être 30, reçu: {strategy.rsi_down_threshold}"

    print("✓ Tous les paramètres par défaut sont corrects")
    print(f"  - RSI seuil baissier: {strategy.rsi_down_threshold} (différent de la stratégie originale: 35)")


def test_signal_logic():
    """Test de la logique des signaux"""
    strategy = TrendPhaseOptimizedStrategy(timeframe="1h")

    print("\n=== Test de la logique des signaux ===")

    # Créer des données pour tester
    base_price = 100.0
    for i in range(100):
        price = base_price + i * 0.5  # Prix en hausse
        candle = {
            'timestamp': i * 60000,
            'open': price,
            'high': price + 0.5,
            'low': price - 0.2,
            'close': price + 0.3,
            'volume': 1000
        }
        strategy.update(candle)

    # Vérifier l'état
    status = strategy.get_status()
    print(f"Structure actuelle: {status['structure']}")
    print(f"Tendance haussière forte: {status['strong_up_trend']}")
    print(f"Tendance baissière forte: {status['strong_down_trend']}")

    ema_short_str = f"{status['indicators']['ema_short']:.2f}" if status['indicators']['ema_short'] else 'None'
    ema_long_str = f"{status['indicators']['ema_long']:.2f}" if status['indicators']['ema_long'] else 'None'
    rsi_str = f"{status['indicators']['rsi']:.2f}" if status['indicators']['rsi'] else 'None'
    adx_str = f"{status['indicators']['adx']:.2f}" if status['indicators']['adx'] else 'None'
    print(f"Indicateurs: EMA courte={ema_short_str}, EMA longue={ema_long_str}, RSI={rsi_str}, ADX={adx_str}")

    print("✓ Indicateurs calculés avec succès")


def test_sell_logic():
    """Test que la logique de vente est uniquement à la fin de tendance haussière"""
    print("\n=== Test de la logique de vente ===")

    strategy = TrendPhaseOptimizedStrategy(timeframe="1h")

    # Simuler que nous étions en tendance haussière
    strategy.previous_strong_up_trend = True
    strategy.strong_up_trend = False  # Fin de tendance haussière
    strategy.strong_down_trend = False  # PAS de début de baisse

    signal = strategy.check_breakout(100.0)
    assert signal == "SELL", f"Devrait générer SELL à la fin de tendance haussière, reçu: {signal}"
    print("✓ Signal SELL généré à la fin de tendance haussière")

    # Reset
    strategy2 = TrendPhaseOptimizedStrategy(timeframe="1h")
    strategy2.previous_strong_down_trend = False
    strategy2.strong_down_trend = True  # Début de baisse mais pas de fin de hausse
    strategy2.previous_strong_up_trend = False
    strategy2.strong_up_trend = False

    signal2 = strategy2.check_breakout(100.0)
    assert signal2 is None, f"Ne devrait PAS générer de signal au début de baisse, reçu: {signal2}"
    print("✓ Pas de signal au début de tendance baissière (conforme au Pine Script)")


def test_registry():
    """Test que la stratégie est bien enregistrée"""
    print("\n=== Test du registry ===")

    strategy = create_strategy('trend_phase_optimized', timeframe='1h')
    assert isinstance(strategy, TrendPhaseOptimizedStrategy), "La stratégie doit être de type TrendPhaseOptimizedStrategy"
    assert strategy.rsi_down_threshold == 30, f"RSI down threshold devrait être 30, reçu: {strategy.rsi_down_threshold}"

    print("✓ Stratégie bien enregistrée dans le registry")
    print(f"  - Accessible via: create_strategy('trend_phase_optimized')")


def main():
    """Fonction principale de test"""
    print("Test de la stratégie TrendPhaseOptimizedStrategy")
    print("Basée sur le Pine Script 'Phases de Tendance (Optimisé+)'\n")

    try:
        test_parameters()
        test_signal_logic()
        test_sell_logic()
        test_registry()

        print("\n" + "="*50)
        print("✓ TOUS LES TESTS PASSÉS AVEC SUCCÈS")
        print("="*50)
        print("\nDifférences avec TrendPhaseStrategy originale:")
        print("  1. RSI seuil baissier: 30 au lieu de 35")
        print("  2. Vente uniquement à la fin de tendance haussière")
        print("     (pas au début de tendance baissière)")

    except AssertionError as e:
        print(f"\n✗ ÉCHEC DU TEST: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
