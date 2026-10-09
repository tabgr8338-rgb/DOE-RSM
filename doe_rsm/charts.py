"""画面アプリ用のグラフ（Plotly）。"""
from typing import Optional, Sequence

import numpy as np
import plotly.graph_objects as go
from scipy import stats as st

from .factors import Factor, Response
from .model import QuadraticFit
from .screening import FirstOrderFit
from .window import slice_map


def _label(f: Factor) -> str:
    return f"{f.name}[{f.unit}]" if f.unit else f.name


def contour(fit: QuadraticFit, response: Response, factors: Sequence[Factor], design_type: str,
            x_factor: int, y_factor: int, fixed: Sequence[float], design_points: Optional[np.ndarray] = None,
            optimum: Optional[Sequence[float]] = None) -> go.Figure:
    """2因子の断面の等高線。塗りは予測値、太線は「予測限界でちょうど規格」の境界（内側が合格側）。"""
    sm = slice_map(fit, response, factors, design_type, x_factor, y_factor, fixed)
    fx, fy = factors[x_factor], factors[y_factor]
    xs = [fx.to_real(v) for v in sm.x_axis]
    ys = [fy.to_real(v) for v in sm.y_axis]
    unit = f"[{response.unit}]" if response.unit else ""
    fig = go.Figure()
    fig.add_trace(go.Contour(x=xs, y=ys, z=sm.pred, colorscale="Viridis", contours=dict(showlabels=True),
                             colorbar=dict(title=f"予測{unit}"), name="予測値",
                             hovertemplate=f"{fx.name}=%{{x:.4g}}<br>{fy.name}=%{{y:.4g}}<br>予測=%{{z:.4g}}<extra></extra>"))
    if np.nanmin(sm.margin) < 0 < np.nanmax(sm.margin):
        fig.add_trace(go.Contour(x=xs, y=ys, z=sm.margin, showscale=False, hoverinfo="skip", name="規格の境界",
                                 contours=dict(start=0, end=0, size=1, coloring="lines", showlabels=False),
                                 colorscale=[[0, "red"], [1, "red"]], line=dict(width=3)))
    if design_points is not None:
        others = [i for i in range(len(factors)) if i not in (x_factor, y_factor)]
        on = np.all(np.isclose(design_points[:, others], np.asarray(fixed)[others]), axis=1) if others else \
            np.ones(len(design_points), bool)
        pts = design_points[on]
        fig.add_trace(go.Scatter(x=[fx.to_real(v) for v in pts[:, x_factor]],
                                 y=[fy.to_real(v) for v in pts[:, y_factor]], mode="markers", name="実験点",
                                 marker=dict(color="white", size=8, line=dict(color="black", width=1))))
    if optimum is not None:
        fig.add_trace(go.Scatter(x=[fx.to_real(optimum[x_factor])], y=[fy.to_real(optimum[y_factor])],
                                 mode="markers", name="ロバスト最適", marker=dict(symbol="star", size=16, color="red")))
    fig.update_layout(xaxis_title=_label(fx), yaxis_title=_label(fy), height=520,
                      legend=dict(orientation="h", y=-0.15), margin=dict(l=10, r=10, t=30, b=10))
    return fig


def residual_plots(fit: QuadraticFit) -> go.Figure:
    """スチューデント化残差（予測値に対して）と正規確率プロット。"""
    from plotly.subplots import make_subplots
    r = fit.studentized_residuals
    fig = make_subplots(rows=1, cols=2, subplot_titles=("残差と予測値", "正規確率プロット"))
    fig.add_trace(go.Scatter(x=fit.fitted, y=r, mode="markers", name="残差",
                             text=[f"標準順{i + 1}" for i in range(len(r))]), 1, 1)
    for v, dash in ((0, "solid"), (3, "dash"), (-3, "dash")):
        fig.add_hline(y=v, line=dict(color="gray", dash=dash, width=1), row=1, col=1)
    (osm, osr), (slope, icpt, _) = st.probplot(r)
    fig.add_trace(go.Scatter(x=osm, y=osr, mode="markers", name="残差（昇順）"), 1, 2)
    fig.add_trace(go.Scatter(x=[osm[0], osm[-1]], y=[icpt + slope * osm[0], icpt + slope * osm[-1]],
                             mode="lines", line=dict(color="gray"), name="正規分布の直線"), 1, 2)
    fig.update_xaxes(title_text="予測値", row=1, col=1)
    fig.update_yaxes(title_text="スチューデント化残差", row=1, col=1)
    fig.update_xaxes(title_text="理論分位点", row=1, col=2)
    fig.update_layout(height=380, showlegend=False, margin=dict(l=10, r=10, t=40, b=10))
    return fig


def pareto(fit: FirstOrderFit, factors: Sequence[Factor]) -> go.Figure:
    """効果の大きさのパレート図。有意（p<0.05、またはLenthのME超え）を赤で示す。"""
    rows = [e for e in fit.effects if e.term != "切片"]
    names = {f"X{i + 1}": f.name for i, f in enumerate(factors)}
    rows.sort(key=lambda e: abs(e.effect))
    active = [(e.p is not None and e.p < 0.05) or (e.p is None and bool(e.lenth_active)) for e in rows]
    fig = go.Figure(go.Bar(x=[abs(e.effect) for e in rows], y=[names.get(e.term, e.term) for e in rows],
                           orientation="h", marker_color=["#C00000" if a else "#8EA9C1" for a in active],
                           text=[f"{e.effect:+.3g}" for e in rows], textposition="outside"))
    if fit.mse is None and fit.lenth_me is not None:
        fig.add_vline(x=fit.lenth_me, line=dict(color="red", dash="dash"), annotation_text="ME（Lenth）")
    fig.update_layout(xaxis_title="効果の大きさ（-1→+1 の変化量の絶対値）", height=120 + 30 * len(rows),
                      margin=dict(l=10, r=10, t=30, b=10))
    return fig
