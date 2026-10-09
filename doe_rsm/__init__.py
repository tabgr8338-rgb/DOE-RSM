"""DOE-RSM：実験計画から応答曲面法による最適条件・工程窓の推定までを支援する分析エンジン。

計算仕様は RSMツール（Excel）v1.1 に合わせ、同梱の架空データで結果が一致することをテストで確認している。
"""
from .canonical import canonical_analysis
from .confirm import judge_confirmation, prediction_interval
from .design import BOX_BEHNKEN, FACE_CCD, ROTATABLE_CCD, build_design, randomize
from .factors import Factor, Response
from .model import fit_quadratic, judgment_gates, term_names
from .optimize import optimize
from .window import combination_check, one_factor_windows, slice_map, window_ranges

__version__ = "0.1.0"
