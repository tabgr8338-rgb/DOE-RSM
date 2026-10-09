"""2次回帰モデル（コード化単位）、ANOVA、適合度の欠如、残差診断、判断ゲート。"""
from dataclasses import dataclass, field
from itertools import combinations
from typing import Dict, List, Optional, Sequence

import numpy as np
from scipy import stats as st


def term_names(k: int) -> List[str]:
    """Excelと同じ並び：切片、1次、交互作用、2乗。"""
    lin = [f"X{i + 1}" for i in range(k)]
    inter = [f"X{i + 1}·X{j + 1}" for i, j in combinations(range(k), 2)]
    sq = [f"X{i + 1}²" for i in range(k)]
    return ["切片"] + lin + inter + sq


def model_matrix(x: np.ndarray) -> np.ndarray:
    x = np.atleast_2d(np.asarray(x, float))
    k = x.shape[1]
    cols = [np.ones(len(x))] + [x[:, i] for i in range(k)]
    cols += [x[:, i] * x[:, j] for i, j in combinations(range(k), 2)]
    cols += [x[:, i] ** 2 for i in range(k)]
    return np.column_stack(cols)


def significance_mark(p: Optional[float]) -> str:
    if p is None:
        return ""
    return "**" if p < 0.01 else "*" if p < 0.05 else "△" if p < 0.1 else ""


@dataclass
class Gate:
    name: str
    status: str   # ○ / △ / × / －
    message: str


@dataclass
class QuadraticFit:
    k: int
    terms: List[str]
    used: np.ndarray
    coef: np.ndarray          # 除外項は0
    se: np.ndarray            # 除外項は nan
    t: np.ndarray
    p: np.ndarray
    cov_unscaled: np.ndarray  # 使用項のみの (X'X)^-1、除外項の行列は0
    x: np.ndarray
    y: np.ndarray
    n: int
    n_params: int
    df_resid: int
    sse: float
    sst: float
    mse: float
    s: float
    leverage: np.ndarray
    residuals: np.ndarray
    press: float
    anova: Dict[str, Dict[str, Optional[float]]]
    confidence: float
    goal: str
    hierarchy_warnings: Dict[str, str] = field(default_factory=dict)

    @property
    def ssr(self) -> float:
        return self.sst - self.sse

    @property
    def r2(self) -> float:
        return 1 - self.sse / self.sst

    @property
    def r2_adj(self) -> float:
        return 1 - (self.sse / self.df_resid) / (self.sst / (self.n - 1))

    @property
    def r2_pred(self) -> float:
        return 1 - self.press / self.sst

    @property
    def fitted(self) -> np.ndarray:
        return self.y - self.residuals

    @property
    def standardized_residuals(self) -> np.ndarray:
        return self.residuals / self.s

    @property
    def studentized_residuals(self) -> np.ndarray:
        h = self.leverage
        out = np.zeros_like(self.residuals)
        ok = h < 0.9999
        out[ok] = self.residuals[ok] / (self.s * np.sqrt(1 - h[ok]))
        return out

    @property
    def t_window(self) -> float:
        """工程窓・最適化の予測限界に使う t。最大化・最小化は片側、目標値は両側。"""
        a = 1 - self.confidence
        q = 1 - a / 2 if self.goal == "target" else 1 - a
        return float(st.t.ppf(q, self.df_resid))

    @property
    def t_confirm(self) -> float:
        """確認実験の判定に使う両側の t。"""
        return float(st.t.ppf(1 - (1 - self.confidence) / 2, self.df_resid))

    def predict(self, x: np.ndarray):
        """予測値と q = x'(X'X)^-1 x を返す。予測の標準誤差は s·√(1+q)。"""
        m = model_matrix(x)
        yhat = m @ self.coef
        q = np.einsum("ij,jk,ik->i", m, self.cov_unscaled, m)
        return yhat, q

    def prediction_limits(self, x: np.ndarray, t_value: Optional[float] = None):
        yhat, q = self.predict(x)
        t_value = self.t_window if t_value is None else t_value
        half = t_value * self.s * np.sqrt(1 + q)
        return yhat, yhat - half, yhat + half

    def coefficient_table(self):
        return [{"term": n, "used": bool(u), "coef": c, "se": s_, "t": t_, "p": p_,
                 "mark": significance_mark(p_ if u else None),
                 "hierarchy": self.hierarchy_warnings.get(n, "")}
                for n, u, c, s_, t_, p_ in zip(self.terms, self.used, self.coef, self.se, self.t, self.p)]


def _hierarchy(k: int, used: np.ndarray) -> Dict[str, str]:
    names = term_names(k)
    lin = {i: used[1 + i] for i in range(k)}
    warn = {}
    idx = 1 + k
    for i, j in combinations(range(k), 2):
        if used[idx] and (not lin[i] or not lin[j]):
            warn[names[idx]] = "主効果が除外されています"
        idx += 1
    for i in range(k):
        if used[idx] and not lin[i]:
            warn[names[idx]] = "主効果が除外されています"
        idx += 1
    return warn


def _pure_error(x: np.ndarray, y: np.ndarray):
    """同一条件の繰り返し（中心点など）から純誤差の平方和と自由度を求める。"""
    groups: Dict[tuple, list] = {}
    for row, v in zip(np.round(x, 9), y):
        groups.setdefault(tuple(row), []).append(v)
    ss, df = 0.0, 0
    for vals in groups.values():
        if len(vals) > 1:
            a = np.asarray(vals)
            ss += float(((a - a.mean()) ** 2).sum())
            df += len(a) - 1
    return ss, df


def fit_quadratic(x: np.ndarray, y: np.ndarray, used: Optional[Sequence[int]] = None,
                  confidence: float = 0.95, goal: str = "maximize") -> QuadraticFit:
    """2次モデルを最小二乗で当てはめる。used で項を0/1指定（切片は常に使用）。"""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    if np.isnan(y).any():
        raise ValueError(f"Yが{int(np.isnan(y).sum())}件未入力")
    k = x.shape[1]
    names = term_names(k)
    used_arr = np.ones(len(names), bool) if used is None else np.asarray(used, bool)
    used_arr[0] = True
    m = model_matrix(x)
    mu = m[:, used_arr]
    n, p = mu.shape
    df_resid = n - p
    if df_resid <= 0:
        raise ValueError(f"残差の自由度が0以下（実験数{n}、項数{p}）")
    xtx_inv_u = np.linalg.inv(mu.T @ mu)
    b_u = xtx_inv_u @ mu.T @ y
    coef = np.zeros(len(names))
    coef[used_arr] = b_u
    cov = np.zeros((len(names), len(names)))
    cov[np.ix_(used_arr, used_arr)] = xtx_inv_u

    resid = y - mu @ b_u
    sse = float(resid @ resid)
    sst = float(((y - y.mean()) ** 2).sum())
    mse = sse / df_resid
    s = mse ** 0.5
    h = np.einsum("ij,jk,ik->i", mu, xtx_inv_u, mu)
    press = float(((resid / (1 - h)) ** 2).sum())

    se = np.full(len(names), np.nan)
    se[used_arr] = np.sqrt(mse * np.diag(xtx_inv_u))
    t = np.full(len(names), np.nan)
    t[used_arr] = b_u / se[used_arr]
    pv = np.full(len(names), np.nan)
    pv[used_arr] = 2 * st.t.sf(np.abs(t[used_arr]), df_resid)

    df_reg = p - 1
    ssr = sst - sse
    f_reg = (ssr / df_reg) / mse
    pe_ss, pe_df = _pure_error(x, y)
    lof_df = df_resid - pe_df
    lof_ss = sse - pe_ss
    if lof_df > 0 and pe_df > 0:
        lof_f = (lof_ss / lof_df) / (pe_ss / pe_df)
        lof_p = float(st.f.sf(lof_f, lof_df, pe_df))
    else:
        lof_f = lof_p = None
    anova = {
        "regression": {"df": df_reg, "ss": ssr, "ms": ssr / df_reg, "f": f_reg,
                       "p": float(st.f.sf(f_reg, df_reg, df_resid))},
        "residual": {"df": df_resid, "ss": sse, "ms": mse, "f": None, "p": None},
        "lack_of_fit": {"df": lof_df, "ss": lof_ss, "ms": lof_ss / lof_df if lof_df > 0 else None,
                        "f": lof_f, "p": lof_p},
        "pure_error": {"df": pe_df, "ss": pe_ss, "ms": pe_ss / pe_df if pe_df > 0 else None,
                       "f": None, "p": None},
        "total": {"df": n - 1, "ss": sst, "ms": None, "f": None, "p": None},
    }
    return QuadraticFit(k, names, used_arr, coef, se, t, pv, cov, x, y, n, p, df_resid, sse, sst, mse, s,
                        h, resid, press, anova, confidence, goal, _hierarchy(k, used_arr))


def judgment_gates(fit: QuadraticFit, design_safe: bool = True, randomization: str = "complete",
                   has_hard_to_change: bool = False, n_missing: int = 0) -> List[Gate]:
    """04_回帰ANOVA の判断ゲート。×があれば最適化に進まない。"""
    gates = []
    gates.append(Gate("計画の安全性", "○", "全実験点が安全限界内") if design_safe else
                 Gate("計画の安全性", "×", "計画が安全限界を超過 → 計画を変更してから実験する"))
    if randomization == "grouped":
        gates.append(Gate("ランダマイズ", "△",
                          "分割区画の順序で実施。この解析は完全ランダムとみなした近似で、変更困難因子のp値は小さく（有意に）出やすい"
                          " → 正式には分割区画解析" if has_hard_to_change else
                          "グループ化を選んでいるが変更困難因子がない（完全ランダムとして生成）"))
    elif has_hard_to_change:
        gates.append(Gate("ランダマイズ", "△", "変更困難因子があるが完全ランダムで生成。現場で実施できるか確認"))
    else:
        gates.append(Gate("ランダマイズ", "○", "完全ランダム"))
    gates.append(Gate("データ", "×", f"Yが{n_missing}件未入力 → 結果は無効") if n_missing else
                 Gate("データ", "○", "全件入力済"))
    reg_p = fit.anova["regression"]["p"]
    gates.append(Gate("回帰の有意性", "○", "回帰は有意") if reg_p < 0.05 else
                 Gate("回帰の有意性", "×", "有意でない → 因子・範囲の見直し。最適化に進まない"))
    lof_p = fit.anova["lack_of_fit"]["p"]
    if lof_p is None:
        gates.append(Gate("適合度の欠如", "－", "純誤差がないため検定不可（中心点を増やす）"))
    elif lof_p < 0.05:
        gates.append(Gate("適合度の欠如", "×", "2次モデルで説明しきれない → 変換・領域縮小・因子追加を検討"))
    else:
        gates.append(Gate("適合度の欠如", "○", "2次モデルで説明できている"))
    if fit.r2 - fit.r2_pred > 0.2:
        gates.append(Gate("R²と予測R²", "△", "差が0.2超 → 過学習の可能性。不要項の除外を検討"))
    else:
        gates.append(Gate("R²と予測R²", "○", "差は0.2以内"))
    big = int((np.abs(fit.studentized_residuals) > 3).sum())
    gates.append(Gate("残差", "△", f"スチューデント化残差の絶対値が3超の点が{big}件 → 消す前に原因を調査") if big else
                 Gate("残差", "○", "スチューデント化残差の絶対値はすべて3以下（グラフでパターンも確認）"))
    if fit.hierarchy_warnings:
        gates.append(Gate("階層性", "△", "主効果を除外した交互作用・2乗項がある: " + ", ".join(fit.hierarchy_warnings)))
    return gates
