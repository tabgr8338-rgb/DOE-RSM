# DOE-RSM

事前実験（スクリーニング）から応答曲面法（RSM）による解析、最適条件・工程窓の推定、確認実験までを支援するソフトです。
いまは画面のない分析エンジン（Pythonパッケージ `doe_rsm`）の段階で、計算仕様は社内の **RSMツール（Excel）v1.1** に合わせています。

## できること

| 段階 | 関数 | 内容 |
|---|---|---|
| スクリーニング | `build_plackett_burman` / `build_full_factorial` / `fit_first_order` | PB計画（8〜24回）・2水準要因計画＋中心点、1次モデルの効果とp値（自由度がなければ Lenth 法） |
| 曲率判定 | `curvature_test` | 要因点と中心点の平均の差で曲率を検定。あればRSMへ、なければ最急上昇法へ |
| 最急上昇法 | `steepest_path` / `recenter` | 1次係数の比で進む経路（最小化なら最急降下）、安全限界の超過表示、次の実験範囲の取り直し |
| 計画 | `build_design` / `randomize` | 面心CCD・回転可能CCD・Box-Behnken、中心点、安全限界チェック、乱数シード付きの実験順序（変更困難因子のグループ化も可） |
| 回帰 | `fit_quadratic` | コード化単位の2次回帰、項の除外（モデル縮小）、階層性チェック、ANOVA、適合度の欠如、R²・調整R²・PRESS・予測R²、スチューデント化残差 |
| 判断ゲート | `judgment_gates` | 安全性・ランダマイズ・データ・回帰の有意性・適合度の欠如・過学習・残差・階層性を ○／△／× で判定 |
| 正準解析 | `canonical_analysis` | 停留点、固有値、最大／最小／鞍点、尾根、領域内外 |
| 最適化 | `optimize` | 領域内グリッド探索で「点予測の最適」と「ロバスト最適（規格側の予測限界と規格の差が最大）」、上位候補、境界警告 |
| 工程窓 | `slice_map` / `one_factor_windows` / `combination_check` | 2因子断面、1因子ずつの窓、提案窓の全組合せ（3^k点）チェック |
| 確認実験 | `judge_confirmation` | 推奨条件での実測が両側予測区間に入るか |

統計上の約束事は Excel v1.1 と同じです。

- 最大化・最小化は片側の予測限界、目標値は両側の予測区間で判定します。確認実験は常に両側です。
- 予測区間が保証するのは「将来の1回の測定値」です。量産での保証は許容区間や工程能力調査（Cpk）で別途確認してください。
- 最適化・工程窓は実験領域内だけを探します（外挿しない。Box-Behnkenは半径√2の球内）。
- 分割区画（変更困難因子）の正式な解析には対応していません。順序のグループ化だけを行い、判断ゲートで △ を出します。

## 使い方

```python
import numpy as np
from doe_rsm import Factor, Response, build_design, randomize, fit_quadratic, judgment_gates, optimize

factors = [Factor("炉温", 55, 75, unit="℃", safety_high=80, hard_to_change=True),
           Factor("乾燥時間", 20, 40, unit="min", safety_low=10),
           Factor("循環風速", 1, 3, unit="m/s", safety_low=0.5, safety_high=4)]
response = Response("剥離強度", goal="maximize", lsl=48.5, confidence=0.95)

design = randomize(build_design(factors, "face_ccd", n_center=6), seed=20261009)
# design.points（標準順のコード値）と design.run_order の順に実験し、Yを測る
y = np.array([...])

fit = fit_quadratic(design.points, y, confidence=response.confidence, goal=response.goal)
for g in judgment_gates(fit, design_safe=design.is_safe, has_hard_to_change=True):
    print(g.status, g.name, g.message)
best = optimize(fit, response, factors, design.design_type)
print(best.robust.x_real, best.robust.margin)
```

## 検証

スクリーニング・曲率判定・最急上昇法は、Montgomery『Design and Analysis of Experiments』の例題（例6.2 ろ過速度、例11.1 化学プロセス）の数値で確かめています。

`tests/fixtures/` に、Excel v1.1 の2・3・4因子版に同梱された架空データ（乾燥炉）と、その計算結果を書き出してあります。
`tests/test_excel_parity.py` で、係数・標準誤差・p値・ANOVA・PRESS・残差・停留点・固有値・ロバスト最適・1因子窓・組合せチェック・確認実験の予測区間が Excel と一致することを確かめています。

```bash
pip install -e ".[dev]"
pytest
```

Excel側を更新したときは、`python tools/extract_excel_fixture.py <xlsx> tests/fixtures/<name>.json` で正解値を作り直せます。

## 今後の予定

- v0.2：Excelでの入出力（プロジェクトファイル）
- v0.3：Streamlitの操作画面
- その先：望ましさ関数による多応答最適化、モンテカルロ、分割区画の正式解析
