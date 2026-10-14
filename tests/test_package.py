import zipfile

import openpyxl
import pytest

from package import package


def _make_root(tmp_path, cached):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S8_Solver"
    ws["B19"] = 1.1228 if cached else "=1+0.1228"      # openpyxl writes a formula with no cached value
    wb.save(tmp_path / "FIN3702B_Portfolio.xlsx")
    (tmp_path / "Prompts_and_Answers.docx").write_bytes(b"docx")
    for f in ("llm_code/optimiser_v1/ai_results.xlsx", "llm_code/mvf_v1/ai_mvf.xlsx"):
        (tmp_path / f).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / f).write_bytes(b"x")


def test_package_ships_the_existing_saved_workbook_and_never_rebuilds_it(tmp_path):
    _make_root(tmp_path, cached=True)
    before = (tmp_path / "FIN3702B_Portfolio.xlsx").read_bytes()
    z = package("B3_Group7", root=tmp_path)
    with zipfile.ZipFile(z) as zf:
        assert zf.read("FIN3702B_Portfolio.xlsx") == before     # byte-identical: Solver output is preserved


def test_package_refuses_a_workbook_with_no_cached_values(tmp_path):
    _make_root(tmp_path, cached=False)
    with pytest.raises(SystemExit, match="open it in Excel"):
        package("B3_Group7", root=tmp_path)


def test_package_refuses_when_workbook_missing(tmp_path):
    _make_root(tmp_path, cached=True)
    (tmp_path / "FIN3702B_Portfolio.xlsx").unlink()
    with pytest.raises(SystemExit, match="not found"):
        package("B3_Group7", root=tmp_path)
