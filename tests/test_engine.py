"""Excelの同梱データでは通らない分岐（BBD・回転可能CCD・モデル縮小・最小化・目標値など）のテスト。"""
import numpy as np
import pytest

from doe_rsm import (BOX_BEHNKEN, ROTATABLE_CCD, Factor, Response, build_design, canonical_analysis,
                     fit_quadratic, judgment_gates, judge_confirmation, optimize, randomize, term_names)
from doe_rsm.optimize import margin
from doe_rsm.window import slice_map

F3 = [Factor("炉温", 55, 75, safety_high=80, hard_to_change=True), Factor("乾燥時間", 20, 40), Factor("風速", 1, 3)]


def test_design_sizes():
    assert build_design(F3, BOX_BEHNKEN, 3).n_runs == 12 + 3
    d = build_design(F3, ROTATABLE_CCD, 6)
    assert d.n_runs == 8 + 6 + 6
    assert d.alpha == pytest.approx(1.681792830507)
    assert build_design(F3[:2], ROTATABLE_CCD, 5).alpha == pytest.approx(2 ** 0.5)
    with pytest.raises(ValueError):
        build_design(F3[:2], BOX_BEHNKEN, 3)


def test_rotatable_ccd_violates_safety_limit():
    # 炉温の安全上限80℃に対し、軸点は 65 + 1.682×10 = 81.8℃
    d = build_design(F3, ROTATABLE_CCD, 6)
    assert not d.is_safe
    assert [r["ok"] for r in d.safety_check()] == [False, True, True]


def test_randomize_is_reproducible_and_groups_hard_to_change():
    a = randomize(build_design(F3, "face_ccd", 6), seed=7).run_order
    b = randomize(build_design(F3, "face_ccd", 6), seed=7).run_order
    assert sorted(a) == list(range(1, 21))
    np.testing.assert_array_equal(a, b)
    d = randomize(build_design(F3, "face_ccd", 6), seed=7, group_hard_to_change=True)
    level_by_run = d.points[np.argsort(d.run_order), 0]
    changes = int((np.diff(level_by_run) != 0).sum())
    assert changes == 2   # 炉温の3水準がまとまっている


def test_reduced_model_matches_lstsq_and_flags_hierarchy():
    rng = np.random.default_rng(1)
    d = build_design(F3, "face_ccd", 6)
    y = 50 + d.points @ [2, 1, 0.5] - 2 * d.points[:, 0] ** 2 + rng.normal(0, 0.3, d.n_runs)
    used = np.ones(10, int)
    used[[2, 6]] = 0          # X2 と X2·X3 を除外
    fit = fit_quadratic(d.points, y, used)
    from doe_rsm.model import model_matrix
    ref, *_ = np.linalg.lstsq(model_matrix(d.points)[:, used.astype(bool)], y, rcond=None)
    np.testing.assert_allclose(fit.coef[used.astype(bool)], ref)
    assert fit.coef[2] == 0 and np.isnan(fit.p[2])
    names = term_names(3)
    assert set(fit.hierarchy_warnings) == {names[4], names[8]}   # X1·X2 と X2²
    assert any(g.name == "階層性" and g.status == "△" for g in judgment_gates(fit))


def test_margin_for_each_goal():
    lo, hi = np.array([9.0]), np.array([11.0])
    assert margin(Response("y", "maximize", lsl=8), lo, hi)[0] == 1
    assert margin(Response("y", "minimize", usl=12), lo, hi)[0] == 1
    assert margin(Response("y", "target", lsl=8.5, usl=11.2, target=10), lo, hi)[0] == pytest.approx(0.2)


def test_target_goal_uses_two_sided_t_and_finds_target():
    d = build_design(F3, "face_ccd", 6)
    x = d.points
    y = 10 + 2 * x[:, 0] + 0.01 * np.sin(np.arange(d.n_runs))
    resp = Response("y", "target", lsl=9, usl=11, target=10)
    fit = fit_quadratic(x, y, confidence=0.95, goal="target")
    assert fit.t_window == pytest.approx(fit.t_confirm)
    r = optimize(fit, resp, F3, "face_ccd")
    assert abs(r.point.pred - 10) < 0.3


def test_minimize_saddle_and_gates():
    d = build_design(F3, "face_ccd", 6)
    x = d.points
    rng = np.random.default_rng(3)
    y = 20 + x[:, 0] ** 2 - x[:, 1] ** 2 + rng.normal(0, 0.1, d.n_runs)
    fit = fit_quadratic(x, y, goal="minimize")
    c = canonical_analysis(fit, "face_ccd", "minimize")
    assert c.kind == "鞍点"
    gates = {g.name: g.status for g in judgment_gates(fit, randomization="complete", has_hard_to_change=True)}
    assert gates["回帰の有意性"] == "○" and gates["ランダマイズ"] == "△"
    r = optimize(fit, Response("y", "minimize", usl=21), F3, "face_ccd")
    assert r.robust.meets_spec and r.on_boundary


def test_slice_and_confirmation():
    d = build_design(F3, "face_ccd", 6)
    y = 50 + d.points[:, 0] - d.points[:, 0] ** 2 + 0.05 * np.cos(np.arange(d.n_runs))
    fit = fit_quadratic(d.points, y)
    resp = Response("y", "maximize", lsl=48)
    m = slice_map(fit, resp, F3, "face_ccd", 0, 1, fixed=[0, 0, 0])
    assert m.pred.shape == (21, 21) and not np.isnan(m.margin).any()
    runs = judge_confirmation(fit, F3, [65, 30, 2], [50.0, 70.0])
    assert runs[0].model_ok and not runs[1].model_ok
    assert runs[0].spec_ok(resp)
