"""スクリーニング（Plackett–Burman・2水準要因計画）、曲率判定、最急上昇法。

流れ：PB／2水準要因で効く因子を絞る → 中心点で曲率を確かめる →
曲率がなければ最急上昇法で応答が良くなる方向へ進む → 曲率が出た領域でCCD／BBDへ。
"""
from dataclasses import dataclass, field
from itertools import combinations
from typing import Dict, List, Optional, Sequence

import numpy as np
from scipy import stats as st

from .design import Design
from .factors import Factor

PLACKETT_BURMAN = "plackett_burman"
FULL_FACTORIAL = "full_factorial"

# Plackett & Burman (1946) の生成行。巡回シフトで N-1 行を作り、最後に全て－の行を足す。
_PB_GENERATORS = {
    8: "+++-+--",
    12: "++-+++---+-",
    16: "++++-+-++--+---",
    20: "++--++++-+-+----++-",
    24: "+++++-+-++--++--+-+----",
}


def plackett_burman_matrix(n_runs: int) -> np.ndarray:
    if n_runs not in _PB_GENERATORS:
        raise ValueError(f"PB計画の実験数は {sorted(_PB_GENERATORS)} のいずれか")
    g = np.array([1.0 if c == "+" else -1.0 for c in _PB_GENERATORS[n_runs]])
    rows = [np.roll(g, i) for i in range(n_runs - 1)]
    rows.append(-np.ones(n_runs - 1))
    return np.array(rows)


def pb_runs_for(k: int) -> int:
    """k因子を割り付けられる最小のPB計画。"""
    return next(n for n in sorted(_PB_GENERATORS) if n - 1 >= k)


def build_plackett_burman(factors: Sequence[Factor], n_runs: Optional[int] = None, n_center: int = 3) -> Design:
    """主効果のスクリーニング用。交互作用は主効果と部分的に交絡するので、絞り込みは確定判断にしない。"""
    k = len(factors)
    n_runs = n_runs or pb_runs_for(k)
    if n_runs - 1 < k:
        raise ValueError(f"{n_runs}回のPB計画には最大{n_runs - 1}因子まで")
    pts = plackett_burman_matrix(n_runs)[:, :k]
    pts = np.vstack([pts, np.zeros((n_center, k))])
    d = Design(list(factors), PLACKETT_BURMAN, pts, ["PB点"] * n_runs + ["中心点"] * n_center)
    d.notes.append("PB計画は主効果のスクリーニング用。交互作用が大きい工程では主効果と交絡するため、絞り込みは確定判断にしない")
    if n_center < 3:
        d.notes.append("中心点が3未満だと曲率と純誤差を十分に評価できない")
    return d


def build_full_factorial(factors: Sequence[Factor], n_center: int = 3, replicates: int = 1) -> Design:
    k = len(factors)
    fact = np.array([[-1.0 if (i >> j) & 1 == 0 else 1.0 for j in range(k)] for i in range(2 ** k)])
    pts = np.vstack([np.tile(fact, (replicates, 1)), np.zeros((n_center, k))])
    return Design(list(factors), FULL_FACTORIAL, pts, ["要因点"] * (len(fact) * replicates) + ["中心点"] * n_center)


@dataclass
class EffectRow:
    term: str
    coef: float
    effect: float           # 効果 = 係数×2（-1→+1 の変化量）
    se: Optional[float]
    t: Optional[float]
    p: Optional[float]
    lenth_active: Optional[bool]


@dataclass
class CurvatureTest:
    mean_factorial: float
    mean_center: float
    ss: float
    f: Optional[float]
    p: Optional[float]
    significant: Optional[bool]
    message: str


@dataclass
class FirstOrderFit:
    terms: List[str]
    coef: np.ndarray
    effects: List[EffectRow]
    df_resid: int
    mse: Optional[float]
    lenth_pse: Optional[float]
    lenth_me: Optional[float]
    curvature: Optional[CurvatureTest]
    notes: List[str] = field(default_factory=list)

    def coef_of(self, name: str) -> float:
        return float(self.coef[self.terms.index(name)])

    def active_factors(self, alpha: float = 0.05) -> List[int]:
        """有意（p値、なければLenth法）と判定された主効果の因子番号（0始まり）。"""
        out = []
        for row in self.effects:
            if "·" in row.term or row.term == "切片":
                continue
            i = int(row.term[1:]) - 1
            if (row.p is not None and row.p < alpha) or (row.p is None and row.lenth_active):
                out.append(i)
        return out


def lenth_pse(effects: np.ndarray) -> float:
    """Lenthの擬似標準誤差。反復のない計画で効果の大きさを判定するのに使う。"""
    a = np.abs(effects)
    s0 = 1.5 * np.median(a)
    return float(1.5 * np.median(a[a < 2.5 * s0]))


def curvature_test(x: np.ndarray, y: np.ndarray) -> Optional[CurvatureTest]:
    """要因点の平均と中心点の平均の差から、曲率（2次の効果）があるかを検定する。"""
    center = np.all(np.isclose(x, 0), axis=1)
    nc, nf = int(center.sum()), int((~center).sum())
    if nc == 0 or nf == 0:
        return None
    yf, yc = float(y[~center].mean()), float(y[center].mean())
    ss = nf * nc * (yf - yc) ** 2 / (nf + nc)
    if nc < 2:
        return CurvatureTest(yf, yc, ss, None, None, None, "中心点が1点のため検定不可（中心点を3点以上に）")
    ms_pe = float(((y[center] - yc) ** 2).sum()) / (nc - 1)
    f = ss / ms_pe if ms_pe > 0 else float("inf")
    p = float(st.f.sf(f, 1, nc - 1))
    sig = p < 0.05
    msg = ("× 曲率あり → 最適点の近くにいる可能性。最急上昇はやめ、この領域でCCD／BBDへ" if sig else
           "○ 曲率は検出されない → 1次モデルで方向を決め、最急上昇法で領域を移す")
    return CurvatureTest(yf, yc, ss, f, p, sig, msg)


def fit_first_order(x: np.ndarray, y: np.ndarray, interactions: bool = False) -> FirstOrderFit:
    """1次モデル（必要なら2因子交互作用つき）。中心点は係数推定に含め、曲率は別に検定する。

    残差の自由度がないとき（反復のない計画を飽和モデルで当てた場合）は Lenth 法で判定する。
    """
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    k = x.shape[1]
    names = ["切片"] + [f"X{i + 1}" for i in range(k)]
    cols = [np.ones(len(y))] + [x[:, i] for i in range(k)]
    if interactions:
        for i, j in combinations(range(k), 2):
            names.append(f"X{i + 1}·X{j + 1}")
            cols.append(x[:, i] * x[:, j])
    m = np.column_stack(cols)
    if np.linalg.matrix_rank(m) < m.shape[1]:
        raise ValueError("計画行列が特異（項が交絡している）。交互作用を外すか計画を見直す")
    xtx_inv = np.linalg.inv(m.T @ m)
    b = xtx_inv @ m.T @ y
    resid = y - m @ b
    df = len(y) - m.shape[1]
    mse = float(resid @ resid) / df if df > 0 else None

    eff = 2 * b[1:]
    pse = me = None
    active = [None] * len(eff)
    if len(eff) >= 3:
        pse = lenth_pse(eff)
        d = len(eff) / 3
        me = float(st.t.ppf(0.975, d) * pse)
        active = [bool(abs(e) > me) for e in eff]

    rows = [EffectRow("切片", float(b[0]), float("nan"), None, None, None, None)]
    for i, name in enumerate(names[1:], start=1):
        se = t = p = None
        if mse is not None:
            se = float(np.sqrt(mse * xtx_inv[i, i]))
            t = float(b[i] / se)
            p = float(2 * st.t.sf(abs(t), df))
        rows.append(EffectRow(name, float(b[i]), float(eff[i - 1]), se, t, p, active[i - 1]))

    fit = FirstOrderFit(names, b, rows, df, mse, pse, me, curvature_test(x, y))
    if mse is None:
        fit.notes.append("残差の自由度がないため、p値の代わりに Lenth 法（ME）で効果を判定")
    return fit


@dataclass
class PathStep:
    step: int
    x: np.ndarray        # コード値
    x_real: np.ndarray
    outside_safety: bool


def steepest_path(fit: FirstOrderFit, factors: Sequence[Factor], goal: str = "maximize",
                  use: Optional[Sequence[int]] = None, base: Optional[int] = None,
                  base_step: float = 1.0, n_steps: int = 10) -> List[PathStep]:
    """最急上昇（最小化なら最急降下）の経路。

    base（既定は係数の絶対値が最大の因子）をコード値で base_step ずつ動かし、
    他の因子は係数の比で動かす。use で経路に使う因子を絞れる（効かない因子は中心に固定）。
    経路上で応答が下がり始めたら、その手前を中心に次の計画（2水準＋中心点、またはCCD）を組む。
    """
    k = len(factors)
    b = np.array([fit.coef_of(f"X{i + 1}") for i in range(k)])
    mask = np.zeros(k, bool)
    mask[list(range(k)) if use is None else list(use)] = True
    b = np.where(mask, b, 0.0)
    if not np.any(b):
        raise ValueError("経路に使う因子の係数がすべて0")
    base = int(np.argmax(np.abs(b))) if base is None else base
    sign = 1.0 if goal == "maximize" else -1.0
    delta = sign * b / abs(b[base]) * base_step
    steps = []
    for s in range(n_steps + 1):
        xc = s * delta
        real = np.array([f.to_real(v) for f, v in zip(factors, xc)])
        outside = any((f.safety_low is not None and r < f.safety_low) or
                      (f.safety_high is not None and r > f.safety_high) for f, r in zip(factors, real))
        steps.append(PathStep(s, xc, real, outside))
    return steps


def recenter(factors: Sequence[Factor], new_center_real: Sequence[float],
             half_ranges: Optional[Sequence[float]] = None) -> List[Factor]:
    """次の実験の因子範囲。新しい中心のまわりに、元の半幅（または指定の半幅）で±1を取り直す。"""
    out = []
    for i, f in enumerate(factors):
        h = f.half_range if half_ranges is None else half_ranges[i]
        c = new_center_real[i]
        out.append(Factor(f.name, c - h, c + h, f.unit, f.safety_low, f.safety_high, f.hard_to_change))
    return out


def screening_summary(fit: FirstOrderFit, factors: Sequence[Factor]) -> Dict[str, object]:
    active = fit.active_factors()
    return {
        "active": [factors[i].name for i in active],
        "inactive": [f.name for i, f in enumerate(factors) if i not in active],
        "curvature": None if fit.curvature is None else fit.curvature.message,
        "notes": fit.notes,
    }
