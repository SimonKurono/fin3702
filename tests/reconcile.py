"""Compare Excel S8_Solver against Python. Usage:
  python tests/reconcile.py FIN3702B_Portfolio.xlsx     # a saved workbook (after Solver was run and saved)
  python tests/reconcile.py --live                      # the workbook currently open in Excel
"""
import subprocess
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import ALL
from optimize import estimation_inputs, mvp, ocp, orp, port_stats

TOL = 0.005
SCALARS = {"MVP return": "B10", "MVP sd": "B12", "ORP return": "B16", "ORP sd": "B18",
           "ORP Sharpe": "B19", "OCP y": "B23", "OCP return": "B26", "OCP sd": "B27"}
WEIGHTS = {"MVP": 9, "ORP": 15}


def _live(cells):
    body = "\n".join(f'set end of out to (value of range "{c}" of worksheet "S8_Solver" of active workbook) as text' for c in cells)
    scr = f'with timeout of 120 seconds\ntell application "Microsoft Excel"\nset out to {{}}\n{body}\nreturn out\nend tell\nend timeout'
    res = subprocess.run(["osascript", "-e", scr], capture_output=True, text=True, timeout=180)
    if res.returncode:
        raise RuntimeError(res.stderr)
    return dict(zip(cells, (float(x) for x in res.stdout.strip().split(", "))))


def _saved(path, cells):
    import openpyxl
    ws = openpyxl.load_workbook(path, data_only=True)["S8_Solver"]
    vals = {c: ws[c].value for c in cells}
    if any(v is None for v in vals.values()):
        raise RuntimeError("No cached values: open the file in Excel, run Solver, and SAVE it first.")
    return vals


def compare(source):
    r, rf_m, st, S, rf = estimation_inputs()
    mu, Sv = st["ret"].values, S.values
    wm, wo = mvp(Sv), orp(mu, Sv, rf)
    o = ocp(wo, mu, Sv, rf, 7)
    py = {"MVP return": port_stats(wm, mu, Sv)[0], "MVP sd": port_stats(wm, mu, Sv)[1],
          "ORP return": port_stats(wo, mu, Sv)[0], "ORP sd": port_stats(wo, mu, Sv)[1],
          "ORP Sharpe": (port_stats(wo, mu, Sv)[0] - rf) / port_stats(wo, mu, Sv)[1],
          "OCP y": o["y"], "OCP return": o["ret"], "OCP sd": o["sd"]}
    wcells = {f"{k} w[{t}]": f"{chr(66 + j)}{row}" for k, row in WEIGHTS.items() for j, t in enumerate(ALL)}
    cells = list(SCALARS.values()) + list(wcells.values())
    got = _live(cells) if source == "--live" else _saved(source, cells)
    wpy = {f"MVP w[{t}]": wm[j] for j, t in enumerate(ALL)} | {f"ORP w[{t}]": wo[j] for j, t in enumerate(ALL)}
    rows = [(n, py[n], got[c], abs(py[n] - got[c])) for n, c in SCALARS.items()]
    rows += [(n, wpy[n], got[c], abs(wpy[n] - got[c])) for n, c in wcells.items()]
    df = pd.DataFrame(rows, columns=["quantity", "python", "excel", "abs_diff"])
    df["ok"] = df.abs_diff <= TOL
    return df


if __name__ == "__main__":
    df = compare(sys.argv[1])
    print(df.round(6).to_string())
    print("ALL OK" if df.ok.all() else "MISMATCH")
