"""RSMツール（Excel v1.1）の同梱データで、計算結果がExcelと一致することを確かめる。"""
import numpy as np
import pytest

from doe_rsm import (build_design, canonical_analysis, combination_check, fit_quadratic, one_factor_windows,
                     optimize, prediction_interval, window_ranges)

REL = 1e-9


def fit_case(case):
    return fit_quadratic(case.x, case.y, confidence=case.response.confidence, goal=case.response.goal)


def test_design_matches_excel_standard_order(case):
    d = build_design(case.factors, case.design_type, n_center=case.data["n_center"])
    np.testing.assert_allclose(d.points, case.x)
    assert d.kinds == [r["kind"] for r in sorted(case.data["runs"], key=lambda r: r["std_order"])]
    assert d.is_safe


def test_coefficients_and_tests(case):
    fit = fit_case(case)
    for row, exp in zip(fit.coefficient_table(), case.expected["terms"]):
        assert row["term"] == exp["term"]
        assert row["coef"] == pytest.approx(exp["coef"], rel=REL, abs=1e-12)
        assert row["se"] == pytest.approx(exp["se"], rel=REL)
        assert row["t"] == pytest.approx(exp["t"], rel=1e-8, abs=1e-10)
        assert row["p"] == pytest.approx(exp["p"], rel=1e-6, abs=1e-12)


def test_summary_statistics(case):
    fit = fit_case(case)
    s = case.expected["stats"]
    assert fit.sse == pytest.approx(s["sse"], rel=REL)
    assert fit.sst == pytest.approx(s["sst"], rel=REL)
    assert fit.ssr == pytest.approx(s["ssr"], rel=REL)
    assert fit.mse == pytest.approx(s["mse"], rel=REL)
    assert fit.s == pytest.approx(s["s"], rel=REL)
    assert fit.r2 == pytest.approx(s["r2"], rel=REL)
    assert fit.r2_adj == pytest.approx(s["r2_adj"], rel=REL)
    assert fit.press == pytest.approx(s["press"], rel=1e-8)
    assert fit.r2_pred == pytest.approx(s["r2_pred"], rel=1e-8)
    assert fit.t_window == pytest.approx(s["t_window"], rel=1e-8)
    assert fit.t_confirm == pytest.approx(s["t_confirm"], rel=1e-8)


def test_anova_and_lack_of_fit(case):
    fit = fit_case(case)
    for key, exp in case.expected["anova"].items():
        got = fit.anova[key]
        for col in ("df", "ss", "ms", "f", "p"):
            if exp[col] is None:
                continue
            assert got[col] == pytest.approx(exp[col], rel=1e-7, abs=1e-12), (key, col)


def test_studentized_residuals(case):
    fit = fit_case(case)
    got = dict(zip(case.std_order, fit.studentized_residuals))
    for std, exp in case.expected["studentized_residuals"].items():
        assert got[int(std)] == pytest.approx(exp, rel=1e-8, abs=1e-10)


def test_canonical_analysis(case):
    fit = fit_case(case)
    c = canonical_analysis(fit, case.design_type, case.response.goal)
    exp = case.expected["canonical"]
    np.testing.assert_allclose(c.stationary_point, exp["stationary_point"], rtol=1e-8)
    assert c.y_at_stationary == pytest.approx(exp["y_at_stationary"], rel=1e-9)
    assert c.distance == pytest.approx(exp["distance"], rel=1e-9)
    assert c.in_region == exp["in_region"]
    # Excelの固有値はJacobi法の反復計算なので、許容差を少し広げる
    np.testing.assert_allclose(c.eigenvalues, exp["eigenvalues"], rtol=1e-6)
    assert c.kind == exp["kind"]


def test_robust_and_point_optimum(case):
    fit = fit_case(case)
    r = optimize(fit, case.response, case.factors, case.design_type)
    for got, exp in ((r.robust, case.expected["optimization"]["robust"]),
                     (r.point, case.expected["optimization"]["point"])):
        np.testing.assert_allclose(got.x, exp["x"], atol=1e-12)
        assert got.pred == pytest.approx(exp["pred"], rel=REL)
        assert got.lower == pytest.approx(exp["lower"], rel=REL)
        assert got.upper == pytest.approx(exp["upper"], rel=REL)
        assert got.margin == pytest.approx(exp["margin"], rel=1e-8)
    for got, exp in zip(r.robust_top, case.expected["optimization"]["robust_top5"]):
        np.testing.assert_allclose(got.x_real, exp["x_real"], atol=1e-9)
        assert got.margin == pytest.approx(exp["margin"], rel=1e-8)


def test_one_factor_windows_and_combination_check(case):
    fit = fit_case(case)
    r = optimize(fit, case.response, case.factors, case.design_type)
    wins = one_factor_windows(fit, case.response, case.factors, case.design_type, r.robust.x)
    for got, exp in zip(wins, case.expected["one_factor_window"]):
        assert got.low == pytest.approx(exp["low"], abs=1e-9)
        assert got.high == pytest.approx(exp["high"], abs=1e-9)
    cc = combination_check(fit, case.response, case.factors, case.design_type, window_ranges(wins, case.factors))
    exp = case.expected["combination_check"]
    assert len(cc.margin) == exp["n_points"]
    assert cc.n_outside == exp["n_outside"]
    assert cc.n_fail == exp["n_fail"]
    assert cc.min_margin == pytest.approx(exp["min_margin"], rel=1e-8)
    np.testing.assert_allclose(cc.worst_real, exp["worst_real"], atol=1e-9)


def test_confirmation_interval_at_robust_optimum(case):
    fit = fit_case(case)
    r = optimize(fit, case.response, case.factors, case.design_type)
    pred, lo, hi = prediction_interval(fit, case.factors, r.robust.x_real)
    exp = case.expected["confirmation_first_row"]
    assert pred == pytest.approx(exp["pred"], rel=REL)
    assert lo == pytest.approx(exp["pi_low"], rel=REL)
    assert hi == pytest.approx(exp["pi_high"], rel=REL)
