import json
from pathlib import Path

import numpy as np
import pytest

from doe_rsm import BOX_BEHNKEN, FACE_CCD, ROTATABLE_CCD, Factor, Response

FIXTURES = Path(__file__).parent / "fixtures"


def design_type_from_label(label: str) -> str:
    if label.startswith("面心"):
        return FACE_CCD
    if label.startswith("回転可能"):
        return ROTATABLE_CCD
    return BOX_BEHNKEN


class ExcelCase:
    def __init__(self, path: Path):
        self.data = json.loads(path.read_text(encoding="utf-8"))
        self.factors = [Factor(**f) for f in self.data["factors"]]
        self.response = Response(**self.data["response"])
        self.design_type = design_type_from_label(self.data["design_type"])
        runs = sorted(self.data["runs"], key=lambda r: r["std_order"])
        self.x = np.array([r["x"] for r in runs])
        self.y = np.array([r["y"] for r in runs])
        self.std_order = [r["std_order"] for r in runs]
        self.expected = self.data["expected"]
        self.k = len(self.factors)


@pytest.fixture(params=[2, 3, 4], ids=lambda k: f"{k}因子")
def case(request):
    return ExcelCase(FIXTURES / f"excel_v1_1_k{request.param}.json")
