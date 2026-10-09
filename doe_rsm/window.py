"""工程窓（Operating Window）：2因子断面、1因子ずつの窓、提案窓の全組合せチェック。

ここでの工程窓は各点の予測限界で判定した「推定工程窓」。確認実験で確かめるまでは
「確認済み工程窓」と区別して扱う。予測区間は将来の1回の測定値に対する区間で、
量産の工程能力（許容区間・Cpk）を保証するものではない。
"""
from dataclasses import dataclass
from itertools import product
from typing import List, Optional, Sequence

import numpy as np

from .design import in_region
from .factors import Factor, Response
from .model import QuadraticFit
from .optimize import INVALID, evaluate

# Excel v1.1 の1因子窓の刻み（因子数ごと）
DEFAULT_WINDOW_STEP = {2: 0.05, 3: 0.025, 4: 0.05}


@dataclass
class SliceMap:
    x_axis: np.ndarray     # 横軸のコード値
    y_axis: np.ndarray     # 縦軸のコード値
    pred: np.ndarray       # [縦, 横]。領域外は nan
    margin: np.ndarray


def slice_map(fit: QuadraticFit, response: Response, factors: Sequence[Factor], design_type: str,
              x_factor: int, y_factor: int, fixed: Sequence[float], step: float = 0.1) -> SliceMap:
    """2因子を動かし、残りは fixed（コード値）に固定した断面。"""
    axis = np.round(np.arange(-1, 1 + step / 2, step), 10)
    xx, yy = np.meshgrid(axis, axis)
    pts = np.tile(np.asarray(fixed, float), (xx.size, 1))
    pts[:, x_factor] = xx.ravel()
    pts[:, y_factor] = yy.ravel()
    yhat, _, _, mg = evaluate(fit, response, pts)
    ok = in_region(pts, factors, design_type)
    shape = xx.shape
    return SliceMap(axis, axis, np.where(ok, yhat, np.nan).reshape(shape), np.where(ok, mg, np.nan).reshape(shape))


@dataclass
class FactorWindow:
    factor: str
    optimum: float
    low: Optional[float]     # コード値。None は最適点自体が規格を満たさない（該当なし）
    high: Optional[float]
    low_real: Optional[float]
    high_real: Optional[float]


def one_factor_windows(fit: QuadraticFit, response: Response, factors: Sequence[Factor], design_type: str,
                       optimum: Sequence[float], step: Optional[float] = None) -> List[FactorWindow]:
    """1因子だけを動かしたときに規格を満たす連続範囲。他の因子は最適点に固定。

    1因子ずつの窓は楽観的（複数因子が同時にずれると外れることがある）ので、
    必ず combination_check で組合せを確認する。
    """
    k = len(factors)
    step = step or DEFAULT_WINDOW_STEP.get(k, 0.05)
    t = np.round(-1 + np.arange(int(round(2 / step)) + 1) * step, 10)
    opt = np.asarray(optimum, float)
    out = []
    for i, f in enumerate(factors):
        pts = np.tile(opt, (len(t), 1))
        pts[:, i] = t
        pts = np.vstack([pts, opt])
        ok = in_region(pts, factors, design_type)
        mg = np.where(ok, evaluate(fit, response, pts)[3], INVALID)
        passed, opt_pass = mg[:-1] >= 0, mg[-1] >= 0
        if not opt_pass:
            out.append(FactorWindow(f.name, opt[i], None, None, None, None))
            continue
        fail_below = t[(~passed) & (t <= opt[i] + 1e-4)]
        fail_above = t[(~passed) & (t >= opt[i] - 1e-4)]
        lo = -1.0 if len(fail_below) == 0 else round(fail_below.max() + step, 4)
        hi = 1.0 if len(fail_above) == 0 else round(fail_above.min() - step, 4)
        out.append(FactorWindow(f.name, opt[i], lo, hi, f.to_real(lo), f.to_real(hi)))
    return out


@dataclass
class CombinationCheck:
    points_real: np.ndarray
    margin: np.ndarray
    valid: np.ndarray
    n_outside: int
    n_fail: int
    min_margin: float
    worst_real: np.ndarray

    @property
    def ok(self) -> bool:
        return self.n_outside == 0 and self.n_fail == 0

    @property
    def verdict(self) -> str:
        if self.n_outside:
            return "× 安全限界・領域外の条件を含む → 窓を狭める"
        if self.n_fail:
            return f"× {self.n_fail}点で規格外のおそれ → 最悪の組合せの方向を狭める"
        return "○ 提案窓の全組合せで、予測限界でも規格を満たす"


def combination_check(fit: QuadraticFit, response: Response, factors: Sequence[Factor], design_type: str,
                      ranges_real: Sequence[Sequence[float]]) -> CombinationCheck:
    """運用したい範囲（実値の下限・上限）について、下限・中央・上限の全組合せ 3^k 点を評価する。"""
    levels = [(lo, lo + (hi - lo) / 2, hi) for lo, hi in ranges_real]
    real = np.array(list(product(*levels)))
    coded = np.column_stack([[f.to_coded(v) for v in real[:, i]] for i, f in enumerate(factors)])
    valid = in_region(coded, factors, design_type)
    mg = evaluate(fit, response, coded)[3]
    worst = int(np.argmin(mg))
    return CombinationCheck(real, mg, valid, int((~valid).sum()), int((mg < 0).sum()), float(mg.min()), real[worst])


def window_ranges(windows: Sequence[FactorWindow], factors: Sequence[Factor]):
    """1因子窓の実値範囲。該当なしの因子は中心に固定（Excelと同じ）。"""
    return [(w.low_real, w.high_real) if w.low is not None else (f.center, f.center)
            for w, f in zip(windows, factors)]
