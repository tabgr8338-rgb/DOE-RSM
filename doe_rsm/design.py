"""実験計画の生成（面心CCD・回転可能CCD・Box-Behnken）、安全限界チェック、ランダマイズ。"""
from dataclasses import dataclass, field
from itertools import combinations, product
from typing import List, Optional, Sequence

import numpy as np

from .factors import EPS, Factor

FACE_CCD = "face_ccd"
ROTATABLE_CCD = "rotatable_ccd"
BOX_BEHNKEN = "box_behnken"
DESIGN_TYPES = (FACE_CCD, ROTATABLE_CCD, BOX_BEHNKEN)


def rotatable_alpha(k: int) -> float:
    return (2 ** k) ** 0.25


def design_alpha(design_type: str, k: int) -> float:
    return rotatable_alpha(k) if design_type == ROTATABLE_CCD else 1.0


def region_radius(design_type: str, k: int) -> Optional[float]:
    """球状の実験領域の半径。面心CCD（立方体の領域）は None。"""
    if design_type == BOX_BEHNKEN:
        return 2 ** 0.5
    if design_type == ROTATABLE_CCD:
        return rotatable_alpha(k)
    return None


@dataclass
class Design:
    factors: List[Factor]
    design_type: str
    points: np.ndarray            # 標準順のコード値 (N, k)
    kinds: List[str]              # 要因点 / 軸点 / BBD点 / 中心点
    run_order: Optional[np.ndarray] = None  # 標準順の各行が何番目に実施されるか（1始まり）
    seed: Optional[int] = None
    notes: List[str] = field(default_factory=list)

    @property
    def k(self) -> int:
        return len(self.factors)

    @property
    def n_runs(self) -> int:
        return len(self.points)

    @property
    def alpha(self) -> float:
        return design_alpha(self.design_type, self.k)

    def real_points(self) -> np.ndarray:
        return np.array([[f.to_real(x) for f, x in zip(self.factors, row)] for row in self.points])

    def safety_check(self):
        """各因子について計画上の最小・最大の実値と安全限界を比べる。"""
        real = self.real_points()
        rows = []
        for i, f in enumerate(self.factors):
            lo, hi = real[:, i].min(), real[:, i].max()
            ok = (f.safety_low is None or lo >= f.safety_low) and (f.safety_high is None or hi <= f.safety_high)
            rows.append({"factor": f.name, "min": lo, "max": hi,
                         "safety_low": f.safety_low, "safety_high": f.safety_high, "ok": ok})
        return rows

    @property
    def is_safe(self) -> bool:
        return all(r["ok"] for r in self.safety_check())


def _factorial(k: int) -> np.ndarray:
    # 標準順：X1 が最も速く切り替わる
    return np.array([[-1 if (i >> j) & 1 == 0 else 1 for j in range(k)] for i in range(2 ** k)], float)


def ccd_points(k: int, alpha: float):
    fact = _factorial(k)
    axial = []
    for j in range(k):
        for s in (-1, 1):
            p = np.zeros(k)
            p[j] = s * alpha
            axial.append(p)
    return np.vstack([fact, np.array(axial)]), ["要因点"] * len(fact) + ["軸点"] * (2 * k)


def bbd_points(k: int):
    if k < 3:
        raise ValueError("Box-Behnken計画は3因子以上")
    pts = []
    for i, j in combinations(range(k), 2):
        for b, a in product((-1, 1), repeat=2):
            p = np.zeros(k)
            p[i], p[j] = a, b
            pts.append(p)
    return np.array(pts), ["BBD点"] * len(pts)


def build_design(factors: Sequence[Factor], design_type: str = FACE_CCD, n_center: int = 6) -> Design:
    if design_type not in DESIGN_TYPES:
        raise ValueError(f"design_type は {DESIGN_TYPES} のいずれか")
    k = len(factors)
    if design_type == BOX_BEHNKEN:
        pts, kinds = bbd_points(k)
    else:
        pts, kinds = ccd_points(k, design_alpha(design_type, k))
    pts = np.vstack([pts, np.zeros((n_center, k))])
    kinds = kinds + ["中心点"] * n_center
    d = Design(list(factors), design_type, pts, kinds)
    if n_center < 3:
        d.notes.append("中心点が3未満のため、適合度の欠如を検定できない（推奨5〜6）")
    return d


def hard_to_change_index(factors: Sequence[Factor]) -> Optional[int]:
    """Excelと同じく、変更困難に○がある最初の因子を使う。"""
    return next((i for i, f in enumerate(factors) if f.hard_to_change), None)


def randomize(design: Design, seed: int, group_hard_to_change: bool = False) -> Design:
    """実験順序を生成する。乱数シードを保存し、同じシードで同じ順序を再現できる。

    group_hard_to_change=True のときは、変更困難因子の水準ごとに実験をまとめる
    （水準の順序もランダム）。解析は完全ランダムとみなした近似になる点に注意。
    """
    rng = np.random.default_rng(seed)
    keys = rng.random(design.n_runs)
    htc = hard_to_change_index(design.factors)
    if group_hard_to_change and htc is not None:
        levels = sorted(set(np.round(design.points[:, htc], 6)))
        level_rank = dict(zip(levels, rng.permutation(len(levels)) + 1))
        keys = np.array([level_rank[round(x, 6)] for x in design.points[:, htc]]) + keys * 0.9
    order = np.empty(design.n_runs, int)
    order[np.argsort(keys, kind="stable")] = np.arange(1, design.n_runs + 1)
    design.run_order = order
    design.seed = seed
    return design


def in_region(x: np.ndarray, factors: Sequence[Factor], design_type: str) -> np.ndarray:
    """安全限界（コード値）の内側か。Box-Behnkenは半径√2の球の内側に限る。x は (..., k)。"""
    x = np.asarray(x, float)
    ok = np.ones(x.shape[:-1], bool)
    for i, f in enumerate(factors):
        ok &= (x[..., i] >= f.safety_low_coded - EPS) & (x[..., i] <= f.safety_high_coded + EPS)
    if design_type == BOX_BEHNKEN:
        ok &= (x ** 2).sum(axis=-1) <= 2 + EPS
    return ok
