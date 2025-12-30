"""
Stratégie de détection de phases de tendance optimisée (Optimisé+).
Basée sur le Pine Script "Phases de Tendance (Optimisé+)".

Cette version utilise des seuils RSI ajustés et une logique de vente
uniquement à la fin des tendances haussières.
"""
from collections import deque
from typing import Dict, Any, Optional
from strategies.base import BaseStrategy


class TrendPhaseOptimizedStrategy(BaseStrategy):
    """
    Stratégie optimisée de détection de phases de tendance.

    Utilise une combinaison d'indicateurs:
    - EMA (Exponential Moving Average) courte et longue
    - RSI (Relative Strength Index)
    - ADX/DMI (Average Directional Index / Directional Movement Index)

    Génère des signaux BUY lors du début d'une tendance haussière forte.
    Génère des signaux SELL uniquement à la fin d'une tendance haussière.

    Différences avec TrendPhaseStrategy:
    - RSI seuil baissier: 30 au lieu de 35
    - Vente uniquement à la fin de tendance haussière (pas au début de baisse)
    """

    def __init__(self, timeframe: str = "1h", **params):
        """
        Initialise la stratégie avec ses paramètres.

        Args:
            timeframe: Intervalle de temps (1m, 5m, 15m, 1h, 4h, 1d)
            **params: Paramètres configurables:
                - ema_short_length: Période EMA courte (défaut: 20)
                - ema_long_length: Période EMA longue (défaut: 50)
                - rsi_length: Période RSI (défaut: 14)
                - adx_length: Période ADX (défaut: 14)
                - adx_smoothing: Lissage ADX (défaut: 14)
                - adx_trend_threshold: Seuil de tendance ADX (défaut: 25)
                - rsi_up_threshold: Seuil RSI haussier (défaut: 55)
                - rsi_down_threshold: Seuil RSI baissier (défaut: 30)
                - max_candles: Nombre max de bougies à garder (défaut: 200)
        """
        super().__init__(timeframe, **params)

        # Paramètres
        self.ema_short_length = params.get('ema_short_length', 20)
        self.ema_long_length = params.get('ema_long_length', 50)
        self.rsi_length = params.get('rsi_length', 14)
        self.adx_length = params.get('adx_length', 14)
        self.adx_smoothing = params.get('adx_smoothing', 14)
        self.adx_trend_threshold = params.get('adx_trend_threshold', 25)
        self.rsi_up_threshold = params.get('rsi_up_threshold', 55)
        self.rsi_down_threshold = params.get('rsi_down_threshold', 30)
        self.max_candles = params.get('max_candles', 200)

        # Données
        self.candles = deque(maxlen=self.max_candles)

        # États
        self.current_structure = None
        self.strong_up_trend = False
        self.strong_down_trend = False
        self.previous_strong_up_trend = False
        self.previous_strong_down_trend = False

        # Signaux
        self.last_signal = None
        self.signal_count = {"BUY": 0, "SELL": 0}

        # Indicateurs calculés
        self.ema_short = None
        self.ema_long = None
        self.previous_ema_short = None
        self.rsi = None
        self.adx = None
        self.plus_di = None
        self.minus_di = None

    def update(self, candle: Dict[str, Any]) -> None:
        """
        Ajoute une bougie et met à jour tous les indicateurs.

        Args:
            candle: Dictionnaire avec clés: timestamp, open, high, low, close, volume
        """
        self.candles.append(candle)
        self._calculate_indicators()
        self._update_trend_state()

    def _calculate_ema(self, prices, period):
        """Calcule l'EMA (Exponential Moving Average)"""
        if len(prices) < period:
            return None

        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period

        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema

        return ema

    def _calculate_rsi(self, prices, period):
        """Calcule le RSI (Relative Strength Index)"""
        if len(prices) < period + 1:
            return None

        gains = []
        losses = []

        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        if len(gains) < period:
            return None

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _calculate_true_range(self, candles):
        """Calcule le True Range pour chaque bougie"""
        tr_values = []

        for i in range(1, len(candles)):
            high = candles[i]['high']
            low = candles[i]['low']
            prev_close = candles[i-1]['close']

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            tr_values.append(tr)

        return tr_values

    def _calculate_directional_movement(self, candles):
        """Calcule +DM et -DM (Directional Movement)"""
        plus_dm = []
        minus_dm = []

        for i in range(1, len(candles)):
            high_diff = candles[i]['high'] - candles[i-1]['high']
            low_diff = candles[i-1]['low'] - candles[i]['low']

            if high_diff > low_diff and high_diff > 0:
                plus_dm.append(high_diff)
                minus_dm.append(0)
            elif low_diff > high_diff and low_diff > 0:
                plus_dm.append(0)
                minus_dm.append(low_diff)
            else:
                plus_dm.append(0)
                minus_dm.append(0)

        return plus_dm, minus_dm

    def _smooth_values(self, values, period):
        """Lisse les valeurs (méthode Wilder's smoothing)"""
        if len(values) < period:
            return None

        smoothed = [sum(values[:period])]

        for i in range(period, len(values)):
            smoothed_value = (smoothed[-1] * (period - 1) + values[i]) / period
            smoothed.append(smoothed_value)

        return smoothed[-1] if smoothed else None

    def _calculate_dmi_adx(self, candles, adx_length, smoothing):
        """Calcule DMI (DI+, DI-) et ADX"""
        if len(candles) < adx_length + smoothing + 1:
            return None, None, None

        # Calcul True Range
        tr_values = self._calculate_true_range(candles)

        # Calcul Directional Movement
        plus_dm, minus_dm = self._calculate_directional_movement(candles)

        if len(tr_values) < adx_length or len(plus_dm) < adx_length:
            return None, None, None

        # Lissage des valeurs
        smoothed_tr = self._smooth_values(tr_values[-adx_length:], adx_length)
        smoothed_plus_dm = self._smooth_values(plus_dm[-adx_length:], adx_length)
        smoothed_minus_dm = self._smooth_values(minus_dm[-adx_length:], adx_length)

        if smoothed_tr is None or smoothed_tr == 0:
            return None, None, None

        # Calcul DI+ et DI-
        plus_di = (smoothed_plus_dm / smoothed_tr) * 100
        minus_di = (smoothed_minus_dm / smoothed_tr) * 100

        # Calcul DX et ADX (simplifié)
        di_sum = plus_di + minus_di
        if di_sum == 0:
            return plus_di, minus_di, None

        dx = abs(plus_di - minus_di) / di_sum * 100

        # ADX est une moyenne mobile du DX (simplifié ici)
        adx = dx  # Simplification: on pourrait faire une vraie EMA du DX

        return plus_di, minus_di, adx

    def _calculate_indicators(self):
        """Calcule tous les indicateurs techniques"""
        if len(self.candles) < max(self.ema_long_length, self.rsi_length, self.adx_length + self.adx_smoothing):
            return

        candles_list = list(self.candles)
        close_prices = [c['close'] for c in candles_list]

        # EMA
        self.ema_short = self._calculate_ema(close_prices, self.ema_short_length)
        self.ema_long = self._calculate_ema(close_prices, self.ema_long_length)

        # EMA précédente (pour détecter la croissance/décroissance)
        if len(close_prices) > self.ema_short_length:
            self.previous_ema_short = self._calculate_ema(close_prices[:-1], self.ema_short_length)
        else:
            self.previous_ema_short = None

        # RSI
        self.rsi = self._calculate_rsi(close_prices, self.rsi_length)

        # DMI et ADX
        self.plus_di, self.minus_di, self.adx = self._calculate_dmi_adx(
            candles_list, self.adx_length, self.adx_smoothing
        )

    def _update_trend_state(self):
        """Met à jour l'état de la tendance"""
        # Sauvegarder les états précédents
        self.previous_strong_up_trend = self.strong_up_trend
        self.previous_strong_down_trend = self.strong_down_trend

        # Vérifier que tous les indicateurs sont calculés
        if (self.ema_short is None or self.ema_long is None or
            self.rsi is None or self.adx is None or
            self.plus_di is None or self.minus_di is None or
            self.previous_ema_short is None):
            self.strong_up_trend = False
            self.strong_down_trend = False
            self.current_structure = None
            return

        # Détection de tendance haussière forte
        self.strong_up_trend = (
            self.ema_short > self.ema_long and
            self.plus_di > self.minus_di and
            self.rsi > self.rsi_up_threshold and
            self.adx > self.adx_trend_threshold and
            self.ema_short > self.previous_ema_short
        )

        # Détection de tendance baissière forte
        self.strong_down_trend = (
            self.ema_short < self.ema_long and
            self.minus_di > self.plus_di and
            self.rsi < self.rsi_down_threshold and
            self.adx > self.adx_trend_threshold and
            self.ema_short < self.previous_ema_short
        )

        # Mise à jour de la structure
        if self.strong_up_trend:
            self.current_structure = "bullish"
        elif self.strong_down_trend:
            self.current_structure = "bearish"
        else:
            self.current_structure = None

    def check_breakout(self, current_price: float) -> Optional[str]:
        """
        Vérifie les signaux de trading basés sur les changements de tendance.

        Conforme au Pine Script:
        - debutHausse: strongUpTrend and not strongUpTrend[1] → BUY
        - finHausse: strongUpTrend[1] and not strongUpTrend → SELL

        Args:
            current_price: Prix actuel

        Returns:
            'BUY', 'SELL', ou None
        """
        # Début de tendance haussière (debutHausse)
        if self.strong_up_trend and not self.previous_strong_up_trend:
            self.last_signal = "BUY"
            self.signal_count["BUY"] += 1
            return "BUY"

        # Fin de tendance haussière uniquement (finHausse)
        if self.previous_strong_up_trend and not self.strong_up_trend:
            self.last_signal = "SELL"
            self.signal_count["SELL"] += 1
            return "SELL"

        return None

    def get_status(self) -> Dict[str, Any]:
        """Retourne le statut actuel de la stratégie"""
        return {
            'structure': self.current_structure,
            'strong_up_trend': self.strong_up_trend,
            'strong_down_trend': self.strong_down_trend,
            'last_signal': self.last_signal,
            'signal_count': self.signal_count,
            'indicators': {
                'ema_short': self.ema_short,
                'ema_long': self.ema_long,
                'rsi': self.rsi,
                'adx': self.adx,
                'plus_di': self.plus_di,
                'minus_di': self.minus_di
            },
            'candles_count': len(self.candles)
        }

    @classmethod
    def get_parameters_schema(cls) -> Dict[str, Any]:
        """Retourne le schéma des paramètres configurables pour l'UI."""
        return {
            'ema_short_length': {
                'type': 'int',
                'default': 20,
                'min': 5,
                'max': 50,
                'description': 'Période de l\'EMA courte'
            },
            'ema_long_length': {
                'type': 'int',
                'default': 50,
                'min': 20,
                'max': 200,
                'description': 'Période de l\'EMA longue'
            },
            'rsi_length': {
                'type': 'int',
                'default': 14,
                'min': 2,
                'max': 30,
                'description': 'Période du RSI'
            },
            'adx_length': {
                'type': 'int',
                'default': 14,
                'min': 5,
                'max': 30,
                'description': 'Période de l\'ADX'
            },
            'adx_smoothing': {
                'type': 'int',
                'default': 14,
                'min': 5,
                'max': 30,
                'description': 'Lissage de l\'ADX'
            },
            'adx_trend_threshold': {
                'type': 'float',
                'default': 25.0,
                'min': 10.0,
                'max': 50.0,
                'description': 'Seuil de tendance ADX'
            },
            'rsi_up_threshold': {
                'type': 'float',
                'default': 55.0,
                'min': 50.0,
                'max': 70.0,
                'description': 'Seuil RSI pour tendance haussière'
            },
            'rsi_down_threshold': {
                'type': 'float',
                'default': 30.0,
                'min': 20.0,
                'max': 50.0,
                'description': 'Seuil RSI pour tendance baissière'
            },
            'max_candles': {
                'type': 'int',
                'default': 200,
                'min': 100,
                'max': 500,
                'description': 'Nombre maximum de bougies à conserver'
            }
        }
