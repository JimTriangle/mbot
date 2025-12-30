"""
Classe de base abstraite pour toutes les stratégies de trading.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List


class BaseStrategy(ABC):
    """
    Classe abstraite définissant l'interface commune pour toutes les stratégies de trading.

    Chaque stratégie doit implémenter:
    - add_candle(): Ajouter une nouvelle bougie
    - update(): Mettre à jour les indicateurs
    - check_breakout(): Vérifier les signaux de trading
    - get_status(): Retourner l'état actuel de la stratégie
    """

    def __init__(self, timeframe: str = "1h", **params):
        """
        Initialise la stratégie avec ses paramètres.

        Args:
            timeframe: Intervalle de temps (1m, 5m, 15m, 1h, 4h, 1d)
            **params: Paramètres spécifiques à chaque stratégie
        """
        self.timeframe = timeframe
        self.params = params
        self.candles: List[Dict[str, Any]] = []

    @abstractmethod
    def update(self, candle: Dict[str, Any]) -> None:
        """
        Ajoute une nouvelle bougie et met à jour tous les indicateurs.

        Args:
            candle: Dictionnaire contenant {open, high, low, close, volume, timestamp}
        """
        pass

    @abstractmethod
    def check_breakout(self, current_price: float) -> Optional[str]:
        """
        Vérifie si un signal de trading est généré.

        Args:
            current_price: Prix actuel

        Returns:
            'BUY', 'SELL', ou None
        """
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """
        Retourne l'état actuel de la stratégie (indicateurs, signaux, etc.).

        Returns:
            Dictionnaire avec les informations de la stratégie
        """
        pass

    @classmethod
    def get_name(cls) -> str:
        """
        Retourne le nom de la stratégie.

        Returns:
            Nom de la stratégie
        """
        return cls.__name__

    @classmethod
    @abstractmethod
    def get_parameters_schema(cls) -> Dict[str, Any]:
        """
        Retourne le schéma des paramètres configurables pour l'UI.

        Returns:
            Dictionnaire décrivant les paramètres:
            {
                'param_name': {
                    'type': 'int'|'float'|'bool'|'str',
                    'default': valeur_par_defaut,
                    'min': valeur_min (optionnel),
                    'max': valeur_max (optionnel),
                    'description': 'Description du paramètre'
                }
            }
        """
        pass

    def get_candles_count(self) -> int:
        """Retourne le nombre de bougies chargées."""
        return len(self.candles)

    def get_latest_candle(self) -> Optional[Dict[str, Any]]:
        """Retourne la dernière bougie ou None."""
        return self.candles[-1] if self.candles else None
