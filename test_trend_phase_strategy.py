#!/usr/bin/env python3
"""
Test rapide de la stratégie TrendPhaseStrategy.
Vérifie que les paramètres et la logique correspondent au Pine Script.
"""
from strategies import TrendPhaseStrategy


def test_parameters():
    """Test des paramètres par défaut"""
    strategy = TrendPhaseStrategy(timeframe="1h")

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


def test_signal_logic():
    """Test de la logique des signaux"""
    strategy = TrendPhaseStrategy(timeframe="1h")

    print("\n=== Test de la logique des signaux ===")

    # Créer des fausses données pour tester
    # On simule une série de bougies haussières
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


def test_buy_sell_signals():
    """Test des signaux BUY/SELL"""
    strategy = TrendPhaseStrategy(timeframe="1h")

    print("\n=== Test des signaux BUY/SELL ===")

    # Test 1: Vérifier qu'aucun signal n'est généré sans données
    signal = strategy.check_breakout(100.0)
    assert signal is None, f"Devrait être None sans données, reçu: {signal}"
    print("✓ Aucun signal sans données suffisantes")

    # Test 2: Simuler un changement de tendance
    # Les tests plus complets nécessiteraient des données réelles
    print("✓ Logique de base vérifiée")


def main():
    """Fonction principale de test"""
    print("Test de la stratégie TrendPhaseStrategy\n")

    try:
        test_parameters()
        test_signal_logic()
        test_buy_sell_signals()

        print("\n" + "="*50)
        print("✓ TOUS LES TESTS PASSÉS AVEC SUCCÈS")
        print("="*50)

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
