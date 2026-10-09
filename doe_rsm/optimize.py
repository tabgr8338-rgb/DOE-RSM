"""領域内のグリッド探索による最適化。

「点予測の最適」と、規格側の予測限界と規格の差（余裕）が最大になる
「ロバスト最適」を並べて出す。原則はロバスト最適を推奨条件にする。
"""
from dataclasses import dataclass
from itertools import product
from typing import List, Optional, Sequence

import numpy as np

from .design import in_region
from .factors import Factor, Response
from .model import QuadraticFit

INVALID = -1e30
# Excel v1.1 のグリッド刻み（因子数ごと）
DEFAULT_GRID_STEP = {2: 0.05, 3: 0.125, 4: 0.25}


def grid_points(k: int, step: float, low: float = -1.0, high: float = 1.0) -> np.ndarray:
    n = int(round((high - low) / step)) + 1
    axis = low + np.arange(n) * step
    # 最後の因子が最も速く切り替わる（Excelの_gridと同じ並び）
    return np.array(list(product(axis, repeat=k)))


def margin(response: Response, lower: np.ndarray, upper: np.ndarray) -> np.ndarray:
    """規格への余裕。≧0 なら予測限界でも規格を満たす。"""
    if response.goal == "maximize":
        return lower - response.lsl
    if response.goal == "minimize":
        return response.usl - upper
    return np.minimum(lower - response.lsl, response.usl - upper)


def point_score(response: Response, yhat: np.ndarray) -> np.ndarray:
    if response.goal == "maximize":
        return yhat
    if response.goal == "minimize":
        return -yhat
    return -np.abs(yhat - response.target)


@dataclass
class Candidate:
    x: np.ndarray       # コード値
    x_real: np.ndarray
    pred: float
    lower: float
    upper: float
    margin: float

    @property
    def meets_spec(self) -> bool:
        return self.margin >= 0


@dataclass
class OptimizationResult:
    robust: Optional[Candidate]
    point: Optional[Candidate]
    robust_top: List[Candidate]
    on_boundary: bool
    warnings: List[str]


def _ranked(score: np.ndarray, valid: np.ndarray) -> np.ndarray:
    # 同点はExcelと同じく後ろの行を優先（行番号×1e-9 を足して比較）
    s = np.where(valid, score, INVALID) + np.arange(len(score)) * 1e-9
    return np.argsort(-s, kind="stable")


def evaluate(fit: QuadraticFit, response: Response, x: np.ndarray):
    yhat, lo, hi = fit.prediction_limits(x)
    return yhat, lo, hi, margin(response, lo, hi)


def optimize(fit: QuadraticFit, response: Response, factors: Sequence[Factor], design_type: str,
             step: Optional[float] = None, top_n: int = 5) -> OptimizationResult:
    k = len(factors)
    step = step or DEFAULT_GRID_STEP.get(k, 0.25)
    x = grid_points(k, step)
    valid = in_region(x, factors, design_type)
    yhat, lo, hi, mg = evaluate(fit, response, x)

    def cand(i):
        if not valid[i]:
            return None
        return Candidate(x[i], np.array([f.to_real(v) for f, v in zip(factors, x[i])]),
                         float(yhat[i]), float(lo[i]), float(hi[i]), float(mg[i]))

    if not valid.any():
        return OptimizationResult(None, None, [], False, ["有効な点なし（安全限界・領域を確認）"])
    order_r = _ranked(mg, valid)
    order_p = _ranked(point_score(response, yhat), valid)
    robust, point = cand(order_r[0]), cand(order_p[0])
    top = [c for c in (cand(i) for i in order_r[:top_n]) if c is not None]

    warnings = []
    on_boundary = bool(np.isclose(np.abs(robust.x), 1).any())
    if on_boundary:
        warnings.append("ロバスト最適が実験範囲の境界上にある。範囲の外にさらに良い条件がある可能性 → 領域を移した追加実験を検討")
    if not robust.meets_spec:
        warnings.append("予測限界では規格を満たせない")
    return OptimizationResult(robust, point, top, on_boundary, warnings)
