"""正準解析：停留点の位置と種類（最大・最小・鞍点）、尾根の有無。"""
from dataclasses import dataclass
from itertools import combinations
from typing import Optional

import numpy as np

from .design import FACE_CCD, region_radius
from .model import QuadraticFit


@dataclass
class CanonicalResult:
    B: np.ndarray
    b: np.ndarray
    stationary_point: Optional[np.ndarray]
    y_at_stationary: Optional[float]
    distance: Optional[float]
    in_region: Optional[bool]
    eigenvalues: np.ndarray
    kind: str        # 最大点 / 最小点 / 鞍点
    has_ridge: bool
    advice: str


def quadratic_parts(fit: QuadraticFit):
    k = fit.k
    b = fit.coef[1:1 + k]
    B = np.zeros((k, k))
    idx = 1 + k
    for i, j in combinations(range(k), 2):
        B[i, j] = B[j, i] = fit.coef[idx] / 2
        idx += 1
    for i in range(k):
        B[i, i] = fit.coef[idx]
        idx += 1
    return B, b


def canonical_analysis(fit: QuadraticFit, design_type: str = FACE_CCD, goal: str = "maximize") -> CanonicalResult:
    B, b = quadratic_parts(fit)
    k = fit.k
    try:
        xs = -0.5 * np.linalg.solve(B, b)
        if not np.all(np.isfinite(xs)) or np.linalg.cond(B) > 1e12:
            raise np.linalg.LinAlgError
    except np.linalg.LinAlgError:
        xs = None
    eig = np.sort(np.linalg.eigvalsh(B))
    kind = "最大点" if eig.max() < 0 else "最小点" if eig.min() > 0 else "鞍点"
    abs_e = np.abs(eig)
    has_ridge = bool(abs_e.min() < 0.1 * abs_e.max())

    if xs is None:
        return CanonicalResult(B, b, None, None, None, None, eig, kind, has_ridge,
                               "停留点を算出できない（2次項を除外している等）→ 最適化の探索結果を使う")
    ys = float(fit.coef[0] + 0.5 * b @ xs)
    dist = float(np.linalg.norm(xs))
    radius = region_radius(design_type, k)
    inside = bool(dist <= radius) if radius is not None else bool(np.abs(xs).max() <= 1)
    if not inside:
        advice = "停留点は実験領域外。外挿値は信用しない → 領域内の探索結果を採用し、必要なら領域を移して追加実験"
    elif (goal == "maximize" and kind == "最大点") or (goal == "minimize" and kind == "最小点"):
        advice = "停留点が領域内の最適点候補。最適化の結果と一致するか確認"
    elif kind == "鞍点":
        advice = "鞍点のため停留点は最適点ではない → 探索結果（領域境界上になりやすい）を採用"
    else:
        advice = "停留点は目的と逆向きの極値 → 探索結果を採用"
    return CanonicalResult(B, b, xs, ys, dist, inside, eig, kind, has_ridge, advice)
