"""
Stratégie 3 swings avec détection de pivots et breakout.
Détecte les structures haussières et baissières basées sur 3 pivots consécutifs.
"""
from collections import deque
from typing import Dict, Any, Optional
from strategies.base import BaseStrategy


class ThreeSwingsStrategy(BaseStrategy):
    """
    Stratégie de détection de structures basée sur 3 pivots (swings).

    Détecte les pivots hauts et bas confirmés avec un lag configurable,
    puis identifie les structures haussières (Higher Highs + Higher Lows)
    ou baissières (Lower Highs + Lower Lows).

    Génère des signaux BUY/SELL sur breakout des niveaux de pivots.
    """

    def __init__(self, timeframe: str = "1h", **params):
        """
        Initialise la stratégie avec ses paramètres.

        Args:
            timeframe: Intervalle de temps (1m, 5m, 15m, 1h, 4h, 1d)
            **params: Paramètres configurables:
                - left: Nombre de bougies à gauche du pivot (défaut: 3)
                - right: Nombre de bougies à droite du pivot (défaut: 3)
                - min_pivot_distance: Distance minimale entre pivots (défaut: 20)
                - breakout_threshold: Seuil de breakout en % (défaut: 0.05)
                - min_structure_strength: Force minimale de structure (défaut: 0.3)
                - signal_cooldown_minutes: Cooldown entre signaux en minutes (défaut: 10)
                - max_pivot_age_minutes: Âge max des pivots en minutes (défaut: 30)
                - max_candles: Nombre max de bougies à garder (défaut: 200)
        """
        super().__init__(timeframe, **params)

        # Paramètres
        self.left = params.get('left', 3)
        self.right = params.get('right', 3)
        self.min_pivot_distance = params.get('min_pivot_distance', 20)
        self.breakout_threshold = params.get('breakout_threshold', 0.05)
        self.min_structure_strength = params.get('min_structure_strength', 0.3)
        self.signal_cooldown_minutes = params.get('signal_cooldown_minutes', 10)
        self.max_pivot_age_minutes = params.get('max_pivot_age_minutes', 30)
        self.max_candles = params.get('max_candles', 200)

        # Données
        self.candles = deque(maxlen=self.max_candles)

        # Pivots confirmés (avec lag)
        self.low1 = None
        self.low2 = None
        self.low3 = None
        self.high1 = None
        self.high2 = None
        self.high3 = None

        self.low1_time = None
        self.high1_time = None

        # État structure
        self.current_structure = None
        self.last_signal = None
        self.last_signal_time = 0
        self.signal_count = {"BUY": 0, "SELL": 0}

        # Niveaux de breakout
        self.buy_level = None  # Niveau à casser pour BUY
        self.sell_level = None  # Niveau à casser pour SELL

    def update(self, candle: Dict[str, Any]) -> None:
        """
        Ajoute une bougie et met à jour tous les indicateurs.

        Args:
            candle: Dictionnaire avec clés: timestamp, open, high, low, close, volume
        """
        self.candles.append(candle)
        self._update_pivots()
        self._update_breakout_levels()

    def _detect_pivot_high(self, index: int) -> Optional[tuple]:
        """Détecte un pivot haut à l'index donné."""
        if index < self.left or index >= len(self.candles) - self.right:
            return None

        candles_list = list(self.candles)
        center_high = candles_list[index]['high']
        center_timestamp = candles_list[index]['timestamp']

        # Vérifier que c'est le plus haut parmi left bougies avant
        for i in range(index - self.left, index):
            if candles_list[i]['high'] >= center_high:
                return None

        # Vérifier que c'est le plus haut parmi right bougies après
        for i in range(index + 1, index + self.right + 1):
            if candles_list[i]['high'] >= center_high:
                return None

        # Vérifier distance minimale avec le pivot précédent
        if self.high1 is not None:
            distance = abs(center_high - self.high1)
            if distance < self.min_pivot_distance:
                return None

        return (center_high, center_timestamp)

    def _detect_pivot_low(self, index: int) -> Optional[tuple]:
        """Détecte un pivot bas à l'index donné."""
        if index < self.left or index >= len(self.candles) - self.right:
            return None

        candles_list = list(self.candles)
        center_low = candles_list[index]['low']
        center_timestamp = candles_list[index]['timestamp']

        # Vérifier que c'est le plus bas parmi left bougies avant
        for i in range(index - self.left, index):
            if candles_list[i]['low'] <= center_low:
                return None

        # Vérifier que c'est le plus bas parmi right bougies après
        for i in range(index + 1, index + self.right + 1):
            if candles_list[i]['low'] <= center_low:
                return None

        # Vérifier distance minimale avec le pivot précédent
        if self.low1 is not None:
            distance = abs(center_low - self.low1)
            if distance < self.min_pivot_distance:
                return None

        return (center_low, center_timestamp)

    def _update_pivots(self) -> None:
        """
        Détecte les pivots CONFIRMÉS (avec right bougies de lag).
        """
        if len(self.candles) < self.left + self.right + 1:
            return

        # Important : On vérifie la bougie qui a right bougies de confirmations
        check_index = len(self.candles) - self.right - 1

        # Pivot bas
        pivot_low_data = self._detect_pivot_low(check_index)
        if pivot_low_data is not None:
            pivot_low, timestamp = pivot_low_data
            self.low3 = self.low2
            self.low2 = self.low1
            self.low1 = pivot_low
            self.low1_time = timestamp

        # Pivot haut
        pivot_high_data = self._detect_pivot_high(check_index)
        if pivot_high_data is not None:
            pivot_high, timestamp = pivot_high_data
            self.high3 = self.high2
            self.high2 = self.high1
            self.high1 = pivot_high
            self.high1_time = timestamp

    def _calculate_structure_strength(self) -> float:
        """Calcule la force de la structure actuelle."""
        if not all([self.low1, self.low2, self.low3, self.high1, self.high2, self.high3]):
            return 0

        low_move_1 = abs(self.low1 - self.low2) / self.low2 * 100
        low_move_2 = abs(self.low2 - self.low3) / self.low3 * 100
        high_move_1 = abs(self.high1 - self.high2) / self.high2 * 100
        high_move_2 = abs(self.high2 - self.high3) / self.high3 * 100

        avg_strength = (low_move_1 + low_move_2 + high_move_1 + high_move_2) / 4
        return avg_strength

    def _check_pivot_freshness(self) -> bool:
        """Vérifie que les pivots ne sont pas trop vieux."""
        if not self.low1_time or not self.high1_time:
            return True

        current_time = list(self.candles)[-1]['timestamp']
        low_age = (current_time - self.low1_time) / 1000 / 60
        high_age = (current_time - self.high1_time) / 1000 / 60

        if low_age > self.max_pivot_age_minutes or high_age > self.max_pivot_age_minutes:
            return False

        return True

    def _analyze_structure(self) -> Optional[str]:
        """Analyse la structure actuelle (haussière ou baissière)."""
        have_3_lows = all(x is not None for x in [self.low1, self.low2, self.low3])
        have_3_highs = all(x is not None for x in [self.high1, self.high2, self.high3])

        if not (have_3_lows and have_3_highs):
            return None

        strength = self._calculate_structure_strength()
        if strength < self.min_structure_strength:
            return None

        if not self._check_pivot_freshness():
            return None

        # Structure haussière : Higher Highs + Higher Lows
        up_structure = (
            self.low1 > self.low2 > self.low3 and
            self.high1 > self.high2 > self.high3
        )

        # Structure baissière : Lower Highs + Lower Lows
        down_structure = (
            self.low1 < self.low2 < self.low3 and
            self.high1 < self.high2 < self.high3
        )

        if up_structure:
            return "bullish"
        elif down_structure:
            return "bearish"
        else:
            return None

    def _update_breakout_levels(self) -> None:
        """Définit les niveaux de breakout EN TEMPS RÉEL."""
        structure = self._analyze_structure()

        if structure == "bullish" and self.high1:
            # Structure haussière : on attend un breakout au-dessus du dernier pivot haut
            self.buy_level = self.high1 * (1 + self.breakout_threshold / 100)
            self.sell_level = None

        elif structure == "bearish" and self.low1:
            # Structure baissière : on attend un breakout en-dessous du dernier pivot bas
            self.sell_level = self.low1 * (1 - self.breakout_threshold / 100)
            self.buy_level = None

        else:
            self.buy_level = None
            self.sell_level = None

    def check_breakout(self, current_price: float) -> Optional[str]:
        """
        Vérifie si le prix actuel casse un niveau de breakout.

        Args:
            current_price: Prix actuel

        Returns:
            'BUY', 'SELL', ou None
        """
        if not self.candles:
            return None

        # Vérifier cooldown
        current_time = list(self.candles)[-1]['timestamp'] / 1000 / 60
        time_since_last = current_time - self.last_signal_time

        if time_since_last < self.signal_cooldown_minutes:
            return None

        # BUY si prix casse le niveau haut
        if self.buy_level and current_price > self.buy_level:
            self.last_signal = "BUY"
            self.signal_count["BUY"] += 1
            self.last_signal_time = current_time
            self.buy_level = None  # Reset niveau
            return "BUY"

        # SELL si prix casse le niveau bas
        if self.sell_level and current_price < self.sell_level:
            self.last_signal = "SELL"
            self.signal_count["SELL"] += 1
            self.last_signal_time = current_time
            self.sell_level = None  # Reset niveau
            return "SELL"

        return None

    def get_status(self) -> Dict[str, Any]:
        """Retourne le statut actuel de la stratégie."""
        strength = self._calculate_structure_strength()
        fresh = self._check_pivot_freshness()

        return {
            'structure': self._analyze_structure(),
            'strength': strength,
            'pivots_fresh': fresh,
            'last_signal': self.last_signal,
            'signal_count': self.signal_count,
            'pivots': {
                'highs': [self.high3, self.high2, self.high1],
                'lows': [self.low3, self.low2, self.low1]
            },
            'breakout_levels': {
                'buy': self.buy_level,
                'sell': self.sell_level
            },
            'candles_count': len(self.candles)
        }

    @classmethod
    def get_parameters_schema(cls) -> Dict[str, Any]:
        """Retourne le schéma des paramètres configurables pour l'UI."""
        return {
            'left': {
                'type': 'int',
                'default': 3,
                'min': 1,
                'max': 10,
                'description': 'Nombre de bougies à gauche du pivot'
            },
            'right': {
                'type': 'int',
                'default': 3,
                'min': 1,
                'max': 10,
                'description': 'Nombre de bougies à droite du pivot (lag de confirmation)'
            },
            'min_pivot_distance': {
                'type': 'float',
                'default': 20.0,
                'min': 1.0,
                'max': 100.0,
                'description': 'Distance minimale entre pivots'
            },
            'breakout_threshold': {
                'type': 'float',
                'default': 0.05,
                'min': 0.01,
                'max': 1.0,
                'description': 'Seuil de breakout en % (ex: 0.05 = 0.05%)'
            },
            'min_structure_strength': {
                'type': 'float',
                'default': 0.3,
                'min': 0.1,
                'max': 2.0,
                'description': 'Force minimale de la structure'
            },
            'signal_cooldown_minutes': {
                'type': 'float',
                'default': 10.0,
                'min': 1.0,
                'max': 60.0,
                'description': 'Cooldown entre signaux (minutes)'
            },
            'max_pivot_age_minutes': {
                'type': 'float',
                'default': 30.0,
                'min': 10.0,
                'max': 120.0,
                'description': 'Âge maximum des pivots (minutes)'
            },
            'max_candles': {
                'type': 'int',
                'default': 200,
                'min': 100,
                'max': 500,
                'description': 'Nombre maximum de bougies à conserver'
            }
        }
