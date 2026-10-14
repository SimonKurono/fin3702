"""Rebuild the workbook and zip the deliverables. Usage: python package.py B#_Group#   (e.g. B3_Group7)"""
import shutil
import sys
from pathlib import Path

from build_workbook import build

name = sys.argv[1]
out = Path(name)
out.mkdir(exist_ok=True)
build("FIN3702B_Portfolio.xlsx")                       # always rebuild so the zip matches the code
for f in ["FIN3702B_Portfolio.xlsx", "Prompts_and_Answers.docx", "llm_code/optimiser_v1/ai_results.xlsx",
          "llm_code/mvf_v1/ai_mvf.xlsx"]:
    shutil.copy(f, out / Path(f).name)
shutil.make_archive(name, "zip", out)
print(f"wrote {name}.zip")
