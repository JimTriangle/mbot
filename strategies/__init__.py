"""
Package de stratégies de trading modulaires.

Ce package contient:
- BaseStrategy: Classe abstraite pour toutes les stratégies
- TrendPhaseStrategy: Stratégie basée sur EMA, RSI et ADX
- ThreeSwingsStrategy: Stratégie basée sur 3 pivots et breakout
- Registry: Système d'enregistrement et d'instanciation des stratégies
"""

from strategies.base import BaseStrategy
from strategies.trend_phase import TrendPhaseStrategy
from strategies.three_swings import ThreeSwingsStrategy
from strategies.registry import (
    STRATEGIES,
    get_strategy_class,
    create_strategy,
    get_all_strategies,
    get_strategy_info,
    get_all_strategies_info
)

__all__ = [
    'BaseStrategy',
    'TrendPhaseStrategy',
    'ThreeSwingsStrategy',
    'STRATEGIES',
    'get_strategy_class',
    'create_strategy',
    'get_all_strategies',
    'get_strategy_info',
    'get_all_strategies_info',
]
