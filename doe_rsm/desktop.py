"""デスクトップアプリとして起動する（Windows のインストーラー版の入口）。

画面アプリ（Streamlit）を自分のPCの中だけで動かし（127.0.0.1）、Edge のアプリ用ウィンドウで開く。
ウィンドウを閉じると画面アプリも止める。Edge が見つからないときは既定のブラウザで開く。

    pythonw DOE-RSM.pyw            # 起動
    python  DOE-RSM.pyw --smoke    # 動作確認（ビルド時のテスト用）：起動して応答を確かめ、終了する
"""
import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import List, Optional

APP_NAME = "DOE-RSM"
NO_WINDOW = 0x08000000 if os.name == "nt" else 0   # CREATE_NO_WINDOW：黒い窓を出さない


def data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    d = Path(base) / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def server_command(port: int) -> List[str]:
    entry = Path(__file__).with_name("app_main.py")
    return [sys.executable, "-m", "streamlit", "run", str(entry),
            "--server.address", "127.0.0.1", "--server.port", str(port), "--server.headless", "true",
            "--server.fileWatcherType", "none", "--browser.gatherUsageStats", "false",
            "--global.developmentMode", "false", "--client.toolbarMode", "minimal"]


def start_server(port: int, log_path: Path) -> subprocess.Popen:
    log = open(log_path, "w", encoding="utf-8", errors="replace")
    return subprocess.Popen(server_command(port), stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            creationflags=NO_WINDOW)


def wait_ready(port: int, proc: subprocess.Popen, timeout: float = 120) -> bool:
    url = f"http://127.0.0.1:{port}/_stcore/health"
    end = time.time() + timeout
    while time.time() < end:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(0.3)
    return False


def find_edge() -> Optional[str]:
    for env in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        root = os.environ.get(env)
        if root:
            p = Path(root) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            if p.exists():
                return str(p)
    return None


def message(text: str) -> None:
    if os.name == "nt":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, APP_NAME, 0x10)
    else:
        print(text, file=sys.stderr)


def smoke(port: int) -> int:
    """ビルドしたアプリが起動し、画面が例外なく描けることを確かめる。"""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(Path(__file__).with_name("app_main.py")), default_timeout=120).run()
    if at.exception:
        print("画面の描画で例外:", at.exception, file=sys.stderr)
        return 1
    next(b for b in at.button if "サンプル" in b.label).click().run()
    if at.exception:
        print("サンプルで例外:", at.exception, file=sys.stderr)
        return 1
    log = data_dir() / "smoke-server.log"
    proc = start_server(port, log)
    try:
        if not wait_ready(port, proc):
            print(log.read_text(encoding="utf-8", errors="replace"), file=sys.stderr)
            return 1
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10) as r:
            ok = r.status == 200
    finally:
        proc.terminate()
        proc.wait(timeout=30)
    print("smoke test ok" if ok else "smoke test failed")
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog=APP_NAME)
    ap.add_argument("--smoke", action="store_true", help="動作確認だけして終了する")
    a = ap.parse_args(argv)
    port = free_port()
    if a.smoke:
        return smoke(port)

    d = data_dir()
    log = d / "server.log"
    proc = start_server(port, log)
    try:
        if not wait_ready(port, proc):
            message(f"{APP_NAME} を起動できませんでした。\n記録：{log}")
            return 1
        url = f"http://127.0.0.1:{port}"
        edge = find_edge()
        if edge:
            # 起動ごとに専用のプロファイルで開くと、この窓を閉じたときにプロセスが終わるので、それを待って画面アプリも止める
            profile = d / "window" / str(port)
            (profile / "Default").mkdir(parents=True, exist_ok=True)
            # 保存のたびに保存先を聞く（既定ではダウンロードフォルダに黙って保存される）
            (profile / "Default" / "Preferences").write_text(
                json.dumps({"download": {"prompt_for_download": True}}), encoding="utf-8")
            win = subprocess.Popen([edge, f"--app={url}", f"--user-data-dir={profile}", "--no-first-run",
                                    "--no-default-browser-check", "--window-size=1400,900"])
            win.wait()
            shutil.rmtree(profile, ignore_errors=True)
        else:
            webbrowser.open(url)
            proc.wait()   # 既定のブラウザでは閉じたことが分からないので、PCの終了まで動かしておく
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
