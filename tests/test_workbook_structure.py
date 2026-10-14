import openpyxl
import pytest
from build_workbook import build

SHEETS = ["Cover", "S1_Summary", "S2_MVF_Excel", "S3_MVF_AI", "S4_Prices",
          "S5_Macro", "S6_Returns", "S7_Cov", "S8_Solver"]


@pytest.fixture(scope="module")
def wb(tmp_path_factory):
    p = tmp_path_factory.mktemp("wb") / "t.xlsx"
    build(str(p))
    return openpyxl.load_workbook(p)           # formulas, not values


def test_all_sheets_present_in_order(wb):
    assert wb.sheetnames == SHEETS


def test_sheet6_and_7_are_formulas_not_hardcodes(wb):
    s6, s7 = wb["S6_Returns"], wb["S7_Cov"]
    for row in s6["B2:K61"]:
        for c in row:
            assert isinstance(c.value, str) and c.value.startswith("=")
    for cell in ("B64", "B65", "B66", "B67"):
        assert str(s6[cell].value).startswith("=")
    for row in s7["B2:K11"]:
        for c in row:
            assert str(c.value).startswith("=") and "COVARIANCE.S" in c.value


def test_estimation_window_is_48_rows(wb):
    assert "B2:B49" in wb["S6_Returns"]["B64"].value
    assert wb["S6_Returns"]["A2"].value.year == 2021 and wb["S6_Returns"]["A49"].value.year == 2024
