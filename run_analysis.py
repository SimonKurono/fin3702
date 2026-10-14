"""Print the Python results for the current ticker set (default 10 ETFs, or FIN_TICKERS=...)."""
import numpy as np

from config import A, ALL, BENCHMARK, CUSTOM
from evaluate import holdout_inputs, metrics, wealth
from forward_model import forward_ocp
from optimize import estimation_inputs, mvp, ocp, orp, port_stats
from robustness import compare_lw


def main():
    r, rf_m, st, S, rf = estimation_inputs()
    mu, cov = st["ret"].values, S.values
    w_mvp, w_orp = mvp(cov), orp(mu, cov, rf)
    o4 = ocp(w_orp, mu, cov, rf, A)
    fwd = forward_ocp()["ocp"]
    print(f"Tickers: {ALL}   benchmark: {BENCHMARK}   rf (2021-24 avg): {rf:.2%}   obs: {len(r)}\n")
    print(st.assign(sharpe=(st['ret'] - rf) / st['sd']).round(4).to_string(), "\n")
    for lab, w in (("MVP", w_mvp), ("ORP", w_orp)):
        ret, sd = port_stats(w, mu, cov)
        print(f"{lab}: return {ret:.2%}  sd {sd:.2%}  Sharpe {(ret - rf) / sd:.2f}  weights " +
              ", ".join(f"{t} {x:.1%}" for t, x in zip(ALL, w) if x > 1e-4))
    print(f"OCP (A={A}): y {o4['y']:.3f}  return {o4['ret']:.2%}  sd {o4['sd']:.2%}  risk-free weight {o4['w_rf']:.1%}")
    print(f"Step 6b OCP (macro ridge, Python replica): y {fwd['y']:.3f}  return {fwd['ret']:.2%}  sd {fwd['sd']:.2%}")
    r25, rf25 = holdout_inputs()
    print("\nStep 8, $100,000 at start of 2025 (buy and hold):")
    for lab, o in (("OCP 4c", o4), ("OCP 6b", fwd)):
        m = metrics(wealth(o["w_risky"], o["w_rf"], r25, rf25), rf25, r25[BENCHMARK])
        print(f"  {lab}: end ${m['end_value']:,.0f}  return {m['total_return']:.1%}  Sharpe {m['sharpe']:.2f}  max drawdown {m['max_drawdown']:.1%}")
    print("\nLedoit-Wolf vs sample ORP weights:")
    print(compare_lw().round(3).to_string())


if __name__ == "__main__":
    main()
