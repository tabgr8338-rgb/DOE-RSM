"""コマンドラインからプロジェクトファイル（Excel）を操作する。

    python -m doe_rsm new 乾燥条件.xlsx --factors 3      # 設定用のファイルを作る → Project・Factorsを入力
    python -m doe_rsm design 乾燥条件.xlsx               # 実験指示書（Designシート）を作る → 実験してYを入力
    python -m doe_rsm analyze 乾燥条件.xlsx              # 解析して結果シートを書き込む
    python -m doe_rsm import RSM_3因子_v1.1.xlsx 取込.xlsx  # 既存のRSMツール（v1.1）から取り込む
"""
import argparse
import sys

from .excel_io import import_excel_v1, read_project, save_project, write_design, write_results, write_template
from .project import RSMResult, analyze


def _print_result(res) -> None:
    if isinstance(res, RSMResult):
        for g in res.gates:
            print(f"  {g.status} {g.name}：{g.message}")
        r = res.optimization.robust
        if r is not None:
            cond = "、".join(f"{v:.4g}" for v in r.x_real)
            print(f"  ロバスト最適：{cond}（予測 {r.pred:.4g}、余裕 {r.margin:.3g}）")
        if res.combination is not None:
            print(f"  工程窓の組合せチェック：{res.combination.verdict}")
    else:
        print(f"  有意な因子：{'、'.join(res.active) or 'なし'}")
        if res.fit.curvature is not None:
            print(f"  曲率：{res.fit.curvature.message}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m doe_rsm", description="DOE-RSM プロジェクトファイルの操作")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new", help="設定用のプロジェクトファイルを作る")
    p.add_argument("path")
    p.add_argument("--factors", type=int, default=3)
    p.add_argument("--title", default="")
    p = sub.add_parser("design", help="設定から実験指示書（Designシート）を作る")
    p.add_argument("path")
    p.add_argument("--force", action="store_true", help="Yが入力済みでも作り直す")
    p = sub.add_parser("analyze", help="Yを読み込んで解析し、結果シートを書き込む")
    p.add_argument("path")
    p = sub.add_parser("import", help="RSMツール（Excel）v1.1 から取り込む")
    p.add_argument("source")
    p.add_argument("dest")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "new":
            write_template(a.path, a.factors, a.title)
            print(f"{a.path} を作成。Project と Factors の黄色セルを入力してから design を実行してください。")
        elif a.cmd == "design":
            project = read_project(a.path)
            d = write_design(a.path, project, a.force)
            print(f"{d.n_runs}回の実験指示書を Design シートに書き込みました。" + ("" if d.is_safe else "（× 安全限界超過あり）"))
            for n in d.notes:
                print(f"  注意：{n}")
        elif a.cmd == "analyze":
            project = read_project(a.path)
            res = analyze(project)
            write_results(a.path, project, res)
            print("解析結果を書き込みました。")
            _print_result(res)
        elif a.cmd == "import":
            save_project(a.dest, import_excel_v1(a.source))
            print(f"{a.dest} に書き出しました。analyze で解析できます。")
    except (ValueError, KeyError, PermissionError) as e:
        print(f"エラー：{e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
