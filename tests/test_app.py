"""画面アプリ：画面がエラーなく出ること、ファイルの読み書き、スクリーニングから応答曲面への引き継ぎ。"""
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from doe_rsm import Factor, Project, Response, analyze  # noqa: E402
from doe_rsm.app import SAMPLE, load_file, project_bytes  # noqa: E402
from doe_rsm.screening import PLACKETT_BURMAN  # noqa: E402

ENTRY = str(Path(__file__).parents[1] / "doe_rsm" / "app_main.py")
FIXTURES = Path(__file__).parent / "fixtures"


def _app(project=None) -> AppTest:
    at = AppTest.from_file(ENTRY, default_timeout=60)
    if project is not None:
        at.session_state["project"] = project
        at.session_state["v"] = 1
        at.session_state["file_name"] = None
        at.session_state["n_new_factors"] = 3
        at.session_state["flash"] = None
    return at.run()


def _texts(at) -> str:
    parts = [m.value for m in at.markdown] + [e.value for e in at.success] + [e.value for e in at.error] + \
            [e.value for e in at.warning] + [e.value for e in at.info]
    return "\n".join(str(p) for p in parts)


def test_empty_start():
    at = _app()
    assert not at.exception
    assert len(at.tabs) == 5


def test_sample_project_all_tabs():
    at = _app()
    next(b for b in at.button if "サンプル" in b.label).click().run()
    assert not at.exception
    text = _texts(at)
    assert "炉温 71.25℃、乾燥時間 37.5min" in text           # ロバスト最適（Excel v1.1 と同じ）
    assert "17点で規格外のおそれ" in text                      # 組合せチェック
    assert len(at.get("plotly_chart")) >= 2                    # 残差・等高線


def test_v1_import_and_save_roundtrip(tmp_path):
    src = FIXTURES / "v1_1" / "RSM_3factor_v1.1.xlsx"
    project = load_file(src.name, src.read_bytes())
    assert project.history[-1][1] == "取り込み"
    res = analyze(project)
    data = project_bytes(project, res)
    again = load_file("saved.xlsx", data)
    np.testing.assert_allclose(again.y, project.y)
    np.testing.assert_array_equal(again.design.run_order, project.design.run_order)
    assert [h[1] for h in again.history][-2:] == ["取り込み", "解析"]
    assert analyze(again).optimization.robust.x_real.tolist() == res.optimization.robust.x_real.tolist()


def test_reject_unknown_workbook(tmp_path):
    from openpyxl import Workbook
    path = tmp_path / "other.xlsx"
    Workbook().save(path)
    with pytest.raises(ValueError, match="プロジェクトファイルでも"):
        load_file("other.xlsx", path.read_bytes())


def test_screening_to_rsm():
    factors = [Factor(f"因子{i + 1}", 10, 20, "", None, None, False) for i in range(5)]
    p = Project("スクリーニング", factors, Response("収率", "maximize", lsl=50), PLACKETT_BURMAN, 3, 7)
    d = p.make_design()
    rng = np.random.default_rng(0)
    p.y = 60 + 4 * d.points[:, 0] + 2.5 * d.points[:, 2] + rng.normal(0, 0.3, d.n_runs)
    at = _app(p)
    assert not at.exception
    assert "因子1、因子3" in _texts(at)
    next(b for b in at.button if "新しいプロジェクト" in b.label).click().run()
    assert not at.exception
    new = at.session_state["project"]
    assert [f.name for f in new.factors] == ["因子1", "因子3"]
    assert new.design is not None and new.n_missing == new.design.n_runs
    assert "スクリーニングから" in new.history[0][2]


def test_sample_file_is_packaged():
    assert SAMPLE.exists()
    assert read_ok(SAMPLE)


def read_ok(path) -> bool:
    from doe_rsm.excel_io import read_project
    return read_project(str(path)).n_missing == 0
