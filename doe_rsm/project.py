"""プロジェクト（1つの実験テーマ）の設定と、計画から解析までを通しで実行する処理。"""
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from .canonical import CanonicalResult, canonical_analysis
from .design import (BOX_BEHNKEN, FACE_CCD, ROTATABLE_CCD, Design, build_design, hard_to_change_index,
                     randomize)
from .factors import Factor, Response
from .model import Gate, QuadraticFit, fit_quadratic, judgment_gates
from .optimize import OptimizationResult, optimize
from .screening import (FULL_FACTORIAL, PLACKETT_BURMAN, FirstOrderFit, PathStep, build_full_factorial,
                        build_plackett_burman, fit_first_order, steepest_path)
from .window import CombinationCheck, FactorWindow, combination_check, one_factor_windows, window_ranges

RSM_TYPES = (FACE_CCD, ROTATABLE_CCD, BOX_BEHNKEN)
SCREENING_TYPES = (PLACKETT_BURMAN, FULL_FACTORIAL)

DESIGN_LABELS = {
    FACE_CCD: "面心CCD",
    ROTATABLE_CCD: "回転可能CCD",
    BOX_BEHNKEN: "Box-Behnken",
    PLACKETT_BURMAN: "Plackett-Burman",
    FULL_FACTORIAL: "2水準要因",
}
GOAL_LABELS = {"maximize": "最大化", "minimize": "最小化", "target": "目標値"}
RANDOMIZATION_LABELS = {"complete": "完全ランダム", "grouped": "変更困難因子でグループ化"}


@dataclass
class Project:
    title: str
    factors: List[Factor]
    response: Response
    design_type: str = FACE_CCD
    n_center: int = 6
    seed: int = 1
    randomization: str = "complete"
    pb_runs: Optional[int] = None
    design: Optional[Design] = None
    y: Optional[np.ndarray] = None          # 標準順。未入力は nan
    used_terms: Optional[List[int]] = None  # 2次モデルで使う項（1/0）。None なら全項
    history: List[List[str]] = field(default_factory=list)

    @property
    def is_screening(self) -> bool:
        return self.design_type in SCREENING_TYPES

    def make_design(self) -> Design:
        if self.design_type == PLACKETT_BURMAN:
            d = build_plackett_burman(self.factors, self.pb_runs, self.n_center)
        elif self.design_type == FULL_FACTORIAL:
            d = build_full_factorial(self.factors, self.n_center)
        else:
            d = build_design(self.factors, self.design_type, self.n_center)
        self.design = randomize(d, self.seed, self.randomization == "grouped")
        self.y = np.full(d.n_runs, np.nan)
        return self.design

    @property
    def n_missing(self) -> int:
        return 0 if self.y is None else int(np.isnan(self.y).sum())


@dataclass
class RSMResult:
    fit: QuadraticFit
    gates: List[Gate]
    canonical: CanonicalResult
    optimization: OptimizationResult
    windows: List[FactorWindow]
    combination: Optional[CombinationCheck]

    @property
    def blocked(self) -> bool:
        return any(g.status == "×" for g in self.gates)


@dataclass
class ScreeningResult:
    fit: FirstOrderFit
    path: List[PathStep]
    active: List[str]


def analyze(project: Project):
    """入力済みのYで解析する。スクリーニング計画なら1次モデル・曲率・最急上昇、RSM計画なら2次モデル以降。"""
    if project.design is None or project.y is None:
        raise ValueError("計画とYがない")
    if project.n_missing:
        raise ValueError(f"Yが{project.n_missing}件未入力")
    x, y = project.design.points, project.y
    if project.is_screening:
        fit = fit_first_order(x, y)
        active = fit.active_factors()
        path = steepest_path(fit, project.factors, project.response.goal, use=active or None) if np.any(fit.coef[1:]) else []
        return ScreeningResult(fit, path, [project.factors[i].name for i in active])

    r = project.response
    fit = fit_quadratic(x, y, project.used_terms, r.confidence, r.goal)
    gates = judgment_gates(fit, project.design.is_safe, project.randomization,
                           hard_to_change_index(project.factors) is not None, project.n_missing)
    canon = canonical_analysis(fit, project.design_type, r.goal)
    opt = optimize(fit, r, project.factors, project.design_type)
    windows, combo = [], None
    if opt.robust is not None:
        windows = one_factor_windows(fit, r, project.factors, project.design_type, opt.robust.x)
        combo = combination_check(fit, r, project.factors, project.design_type,
                                  window_ranges(windows, project.factors))
    return RSMResult(fit, gates, canon, opt, windows, combo)
