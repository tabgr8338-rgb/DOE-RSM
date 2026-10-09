"""確認実験：推奨条件での実測値が両側予測区間に入るかを判定する。"""
from dataclasses import dataclass
from typing import List, Sequence

import numpy as np

from .factors import Factor, Response
from .model import QuadraticFit


@dataclass
class ConfirmationRun:
    x_real: np.ndarray
    observed: float
    pred: float
    pi_low: float
    pi_high: float

    @property
    def model_ok(self) -> bool:
        return self.pi_low <= self.observed <= self.pi_high

    def spec_ok(self, response: Response) -> bool:
        if response.lsl is not None and self.observed < response.lsl:
            return False
        return not (response.usl is not None and self.observed > response.usl)


def prediction_interval(fit: QuadraticFit, factors: Sequence[Factor], x_real: Sequence[float]):
    coded = np.array([[f.to_coded(v) for f, v in zip(factors, x_real)]])
    yhat, lo, hi = fit.prediction_limits(coded, fit.t_confirm)
    return float(yhat[0]), float(lo[0]), float(hi[0])


def judge_confirmation(fit: QuadraticFit, factors: Sequence[Factor], x_real: Sequence[float],
                       observed: Sequence[float]) -> List[ConfirmationRun]:
    """同条件で3回以上を推奨。平均も個々も区間内ならモデルを採用、外れたら計画・モデルを見直す。"""
    pred, lo, hi = prediction_interval(fit, factors, x_real)
    return [ConfirmationRun(np.asarray(x_real, float), float(y), pred, lo, hi) for y in observed]
