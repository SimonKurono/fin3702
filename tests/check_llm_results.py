"""Compare an LLM script's results.json with the Python reference. Usage: python tests/check_llm_results.py results.json"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from optimize import estimation_inputs, mvp, ocp, orp, port_stats

TOL = 0.005
r, rf_m, st, S, rf = estimation_inputs()
mu, Sv = st["ret"].values, S.values
truth = {"mvp": mvp(Sv), "orp": orp(mu, Sv, rf)}
got = json.load(open(sys.argv[1]))
ok = True
for k, w in truth.items():
    ret, sd = port_stats(w, mu, Sv)
    for q, t in (("ret", ret), ("sd", sd)):
        d = abs(got[k][q] - t); ok &= d <= TOL
        print(f"{k} {q}: LLM {got[k][q]:.6f} vs Python {t:.6f}  diff {d:.6f}  {'OK' if d <= TOL else 'FAIL'}")
o = ocp(truth["orp"], mu, Sv, rf, 7)
for q in ("ret", "sd"):
    d = abs(got["ocp"][q] - o[q]); ok &= d <= TOL
    print(f"ocp {q}: LLM {got['ocp'][q]:.6f} vs Python {o[q]:.6f}  diff {d:.6f}  {'OK' if d <= TOL else 'FAIL'}")
print("PASS" if ok else "FAIL")
