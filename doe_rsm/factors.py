"""因子と目的変数の定義、コード化（-1〜+1）と実値の変換。"""
from dataclasses import dataclass
from typing import Optional

# Excelと同じく、安全限界が未入力のときはコード値で ±99 を使う
NO_LIMIT = 99.0
EPS = 1e-9


@dataclass
class Factor:
    name: str
    low: float
    high: float
    unit: str = ""
    safety_low: Optional[float] = None
    safety_high: Optional[float] = None
    hard_to_change: bool = False

    @property
    def center(self) -> float:
        return (self.low + self.high) / 2

    @property
    def half_range(self) -> float:
        return (self.high - self.low) / 2

    def to_coded(self, value: float) -> float:
        return (value - self.center) / self.half_range

    def to_real(self, coded: float) -> float:
        return self.center + coded * self.half_range

    @property
    def safety_low_coded(self) -> float:
        return -NO_LIMIT if self.safety_low is None else self.to_coded(self.safety_low)

    @property
    def safety_high_coded(self) -> float:
        return NO_LIMIT if self.safety_high is None else self.to_coded(self.safety_high)


GOALS = ("maximize", "minimize", "target")


@dataclass
class Response:
    """目的変数。goal は maximize / minimize / target。"""
    name: str
    goal: str
    lsl: Optional[float] = None
    usl: Optional[float] = None
    target: Optional[float] = None
    confidence: float = 0.95
    unit: str = ""

    def __post_init__(self):
        if self.goal not in GOALS:
            raise ValueError(f"goal は {GOALS} のいずれか: {self.goal}")
        if self.goal == "maximize" and self.lsl is None:
            raise ValueError("最大化には下限規格 LSL が必要")
        if self.goal == "minimize" and self.usl is None:
            raise ValueError("最小化には上限規格 USL が必要")
        if self.goal == "target" and None in (self.lsl, self.usl, self.target):
            raise ValueError("目標値には LSL・USL・T がすべて必要")
