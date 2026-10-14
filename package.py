"""Zip the deliverables. Usage: python package.py B#_Group#   (e.g. B3_Group7)

The workbook is NEVER rebuilt here: the file shipped must be the one you ran Solver on and saved in Excel
(a rebuilt file would overwrite the Solver output and has no cached values). Rebuild explicitly with
`python build_workbook.py` before running Solver."""
import shutil
import sys
import zipfile
from pathlib import Path

FILES = ["FIN3702B_Portfolio.xlsx", "Prompts_and_Answers.docx", "llm_code/optimiser_v1/ai_results.xlsx",
         "llm_code/mvf_v1/ai_mvf.xlsx"]


def package(name, root=None):
    root = Path(root) if root else Path(__file__).parent
    wb_path = root / FILES[0]
    if not wb_path.exists():
        raise SystemExit(f"{FILES[0]} not found: run build_workbook.py, run Solver in Excel, and save it first.")
    import openpyxl
    cached = openpyxl.load_workbook(wb_path, data_only=True)["S8_Solver"]["B19"].value
    if cached is None:
        raise SystemExit(f"{FILES[0]} has no cached values: open it in Excel, run Solver on S8_Solver, and save "
                         "(Cmd+S) before packaging.")
    out = root / name
    out.mkdir(exist_ok=True)
    for f in FILES:
        shutil.copy(root / f, out / Path(f).name)
    return Path(shutil.make_archive(str(out), "zip", out))


if __name__ == "__main__":
    print(f"wrote {package(sys.argv[1])}")
