"""
Registry des stratégies de trading disponibles.
Permet d'instancier facilement une stratégie par son nom.
"""
from typing import Dict, Type, Any
from strategies.base import BaseStrategy
from strategies.trend_phase import TrendPhaseStrategy
from strategies.three_swings import ThreeSwingsStrategy


# Registry global des stratégies disponibles
STRATEGIES: Dict[str, Type[BaseStrategy]] = {
    "trend_phase": TrendPhaseStrategy,
    "three_swings": ThreeSwingsStrategy,
}


def get_strategy_class(strategy_name: str) -> Type[BaseStrategy]:
    """
    Récupère la classe d'une stratégie par son nom.

    Args:
        strategy_name: Nom de la stratégie (clé dans STRATEGIES)

    Returns:
        Classe de la stratégie

    Raises:
        KeyError: Si la stratégie n'existe pas
    """
    if strategy_name not in STRATEGIES:
        available = ", ".join(STRATEGIES.keys())
        raise KeyError(
            f"Stratégie '{strategy_name}' introuvable. "
            f"Stratégies disponibles: {available}"
        )
    return STRATEGIES[strategy_name]


def create_strategy(strategy_name: str, timeframe: str = "1h", **params) -> BaseStrategy:
    """
    Crée une instance de stratégie.

    Args:
        strategy_name: Nom de la stratégie
        timeframe: Intervalle de temps (1m, 5m, 15m, 1h, 4h, 1d)
        **params: Paramètres spécifiques à la stratégie

    Returns:
        Instance de la stratégie

    Raises:
        KeyError: Si la stratégie n'existe pas
    """
    strategy_class = get_strategy_class(strategy_name)
    return strategy_class(timeframe=timeframe, **params)


def get_all_strategies() -> Dict[str, Type[BaseStrategy]]:
    """
    Retourne toutes les stratégies disponibles.

    Returns:
        Dictionnaire {nom: classe}
    """
    return STRATEGIES.copy()


def get_strategy_info(strategy_name: str) -> Dict[str, Any]:
    """
    Retourne les informations d'une stratégie (nom, schéma des paramètres).

    Args:
        strategy_name: Nom de la stratégie

    Returns:
        Dictionnaire avec:
            - name: Nom de la classe
            - key: Clé dans le registry
            - parameters: Schéma des paramètres
            - description: Docstring de la classe

    Raises:
        KeyError: Si la stratégie n'existe pas
    """
    strategy_class = get_strategy_class(strategy_name)
    return {
        'name': strategy_class.get_name(),
        'key': strategy_name,
        'parameters': strategy_class.get_parameters_schema(),
        'description': strategy_class.__doc__.strip() if strategy_class.__doc__ else ""
    }


def get_all_strategies_info() -> Dict[str, Dict[str, Any]]:
    """
    Retourne les informations de toutes les stratégies.

    Returns:
        Dictionnaire {nom: info}
    """
    return {
        name: get_strategy_info(name)
        for name in STRATEGIES.keys()
    }
