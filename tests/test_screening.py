"""スクリーニング・曲率判定・最急上昇法のテスト。数値は Montgomery『Design and Analysis of Experiments』の例題。"""
import numpy as np
import pytest

from doe_rsm import Factor, randomize
from doe_rsm.screening import (build_full_factorial, build_plackett_burman, curvature_test, fit_first_order,
                               lenth_pse, plackett_burman_matrix, pb_runs_for, recenter, steepest_path)


@pytest.mark.parametrize("n", [8, 12, 16, 20, 24])
def test_plackett_burman_is_orthogonal_and_balanced(n):
    m = plackett_burman_matrix(n)
    assert m.shape == (n, n - 1)
    np.testing.assert_allclose(m.T @ m, n * np.eye(n - 1))
    np.testing.assert_allclose(m.sum(axis=0), 0)


def test_pb_design_size_and_notes():
    factors = [Factor(f"F{i}", 0, 10) for i in range(7)]
    assert pb_runs_for(7) == 8 and pb_runs_for(8) == 12
    d = randomize(build_plackett_burman(factors, n_center=3), seed=1)
    assert d.n_runs == 11 and d.kinds.count("中心点") == 3
    assert any("交絡" in n for n in d.notes)
    with pytest.raises(ValueError):
        build_plackett_burman([Factor(f"F{i}", 0, 1) for i in range(8)], n_runs=8)


# Montgomery 例11.1（化学プロセス）：反応時間 35±5 min、温度 155±5 ℉、2^2 ＋中心点5
CHEM_X = np.array([[-1, -1], [1, -1], [-1, 1], [1, 1], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]], float)
CHEM_Y = np.array([39.3, 40.9, 40.0, 41.5, 40.3, 40.5, 40.7, 40.2, 40.6])
CHEM_F = [Factor("反応時間", 30, 40, "min"), Factor("温度", 150, 160, "℉")]


def test_first_order_model_example_11_1():
    fit = fit_first_order(CHEM_X, CHEM_Y)
    assert fit.coef_of("X1") == pytest.approx(0.775)
    assert fit.coef_of("X2") == pytest.approx(0.325)
    assert fit.coef_of("切片") == pytest.approx(40.44444, abs=1e-4)


def test_curvature_example_11_1():
    c = curvature_test(CHEM_X, CHEM_Y)
    assert c.mean_factorial == pytest.approx(40.425)
    assert c.mean_center == pytest.approx(40.46)
    assert c.ss == pytest.approx(0.0027, abs=1e-4)
    assert c.f == pytest.approx(0.0027222 / 0.043, rel=1e-3)
    assert not c.significant


def test_steepest_ascent_path_example_11_1():
    fit = fit_first_order(CHEM_X, CHEM_Y)
    path = steepest_path(fit, CHEM_F, "maximize", n_steps=12)
    # 基準は反応時間：コードで1ずつ（5 min）、温度は 0.325/0.775 = 0.42 ずつ
    np.testing.assert_allclose(path[1].x, [1.0, 0.325 / 0.775])
    np.testing.assert_allclose(path[1].x_real, [40.0, 155 + 5 * 0.325 / 0.775])
    np.testing.assert_allclose(path[10].x_real[0], 85.0)
    descent = steepest_path(fit, CHEM_F, "minimize", n_steps=1)
    assert descent[1].x[0] == -1.0


def test_steepest_path_respects_safety_and_selection():
    f = [Factor("時間", 30, 40, safety_high=52), Factor("温度", 150, 160)]
    fit = fit_first_order(CHEM_X, CHEM_Y)
    path = steepest_path(fit, f, use=[0], n_steps=4)
    assert all(s.x[1] == 0 for s in path)
    assert [s.outside_safety for s in path] == [False, False, False, False, True]


def test_recenter():
    nf = recenter(CHEM_F, [85, 175])
    assert (nf[0].low, nf[0].high, nf[1].low, nf[1].high) == (80, 90, 170, 180)


# Montgomery 例6.2（ろ過速度）：2^4 反復なし。効果 A=21.625, C=9.875, D=14.625, AC=-18.125, AD=16.625
FILTRATION_Y = np.array([45, 71, 48, 65, 68, 60, 80, 65, 43, 100, 45, 104, 75, 86, 70, 96], float)


def test_effects_and_significance_example_6_2():
    factors = [Factor(n, -1, 1) for n in "ABCD"]
    d = build_full_factorial(factors, n_center=0)
    fit = fit_first_order(d.points, FILTRATION_Y, interactions=True)
    eff = {r.term: r.effect for r in fit.effects}
    assert eff["X1"] == pytest.approx(21.625)
    assert eff["X2"] == pytest.approx(3.125)
    assert eff["X3"] == pytest.approx(9.875)
    assert eff["X4"] == pytest.approx(14.625)
    assert eff["X1·X3"] == pytest.approx(-18.125)
    assert eff["X1·X4"] == pytest.approx(16.625)
    assert fit.active_factors() == [0, 2, 3]
    assert fit.curvature is None


def test_lenth_flags_large_effects_when_saturated():
    # 7因子のPB8に中心点なし → 残差自由度0なので Lenth 法で判定する
    rng = np.random.default_rng(0)
    x = plackett_burman_matrix(8)
    y = 50 + 6 * x[:, 0] - 4 * x[:, 3] + rng.normal(0, 0.2, 8)
    fit = fit_first_order(x, y)
    assert fit.df_resid == 0 and fit.mse is None
    assert fit.active_factors() == [0, 3]
    assert lenth_pse(np.array([1.0, -1.0, 0.5, 20.0])) > 0
