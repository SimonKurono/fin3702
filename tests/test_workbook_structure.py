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


def test_solver_sheet_layout_and_formulas(wb):
    s = wb["S8_Solver"]
    assert str(s["B11"].value).startswith("=SUMPRODUCT(MMULT(B9:K9")
    assert "COUNTIF" in s["B20"].value and str(s["B19"].value).startswith("=")
    assert s["B29"].value == 7
    assert "B23*B15" in s["B24"].value.replace("$", "")
    for c in ("B9", "K9", "B15", "K15", "B23"):          # Solver decision variables are numbers
        assert isinstance(s[c].value, (int, float))


def test_chart_and_summary_exist(tmp_path_factory):
    import zipfile
    p = tmp_path_factory.mktemp("c") / "c.xlsx"
    build(str(p))
    assert any(n.startswith("xl/charts/chart") for n in zipfile.ZipFile(p).namelist())
    s1 = openpyxl.load_workbook(p)["S1_Summary"]
    for c in ("B17", "C17", "D17", "E17", "B18", "B19"):  # return / sd / sharpe are formulas
        assert str(s1[c].value).startswith("=")
    assert str(s1["B4"].value).startswith("=S8_Solver!")


def test_solver_preload_names_defined(tmp_path_factory):
    p = tmp_path_factory.mktemp("n") / "n.xlsx"
    build(str(p))
    names = openpyxl.load_workbook(p)["S8_Solver"].defined_names
    assert "solver_opt" in names and "solver_adj" in names


def test_equal_start_option_gives_solver_a_real_job(tmp_path):
    p = tmp_path / "eq.xlsx"
    build(str(p), equal_start=True)
    s = openpyxl.load_workbook(p)["S8_Solver"]
    assert all(abs(s.cell(9, 2 + j).value - 0.1) < 1e-12 for j in range(10))
    assert all(abs(s.cell(15, 2 + j).value - 0.1) < 1e-12 for j in range(10))
    assert abs(s["B23"].value - 0.5) < 1e-12
