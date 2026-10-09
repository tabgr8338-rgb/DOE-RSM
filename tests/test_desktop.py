"""デスクトップ版の起動処理：画面アプリを自分のPCの中だけで動かし、起動を確かめられること。"""
import pytest

pytest.importorskip("streamlit")
from doe_rsm import desktop  # noqa: E402


def test_server_listens_only_on_this_pc():
    cmd = desktop.server_command(8765)
    assert cmd[cmd.index("--server.address") + 1] == "127.0.0.1"
    assert cmd[cmd.index("--server.headless") + 1] == "true"


def test_smoke_starts_and_stops_server():
    assert desktop.smoke(desktop.free_port()) == 0
