# FIN3702B Portfolio Project Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce the Excel workbook, the LLM prompts document (with Step 8 and 9 answers), and demo support for the FIN3702B group project, targeting 95%+ on every rubric criterion.

**Architecture:** Python is the source of truth (data, optimiser, forward model, evaluation, robustness). `build_workbook.py` writes an Excel file with live formulas that mirror the Python maths; the user runs Solver on Sheet 8 and a reconciliation test confirms Excel and Python agree. LLM-generated code is tested against the same Python core.

**Tech Stack:** Python 3.13, pandas, numpy, scipy, scikit-learn, yfinance, xlsxwriter, openpyxl, matplotlib, python-docx, pytest.

**Spec:** `docs/superpowers/specs/2026-10-14-fin3702b-portfolio-project-design.md`

## Global Constraints

- Project lives in `~/Developer/FIN3702B_Project` (outside iCloud). Venv: `.venv/`. Run tests with `.venv/bin/pytest`.
- ETFs (10): equity SPY, IWM, VEA, VWO, XLE, QQQ; bonds AGG, TIP, HYG; alternative GLD.
- Prices: month-end adjusted close. Dec 2020 is the base price, so Jan 2021 to Dec 2024 gives 48 monthly returns for Steps 3-4. 2025 is hold-out (Steps 7-8 only).
- Annualised return = arithmetic monthly mean x 12. Annualised st. dev. = sample st. dev. (`STDEV.S`) x sqrt(12). Rf = French `RF` column / 100, annualised as mean monthly RF x 12.
- No shorting anywhere (MVP, ORP, frontier). ORP must hold at least 2 ETFs with weight above 0.0001. OCP may borrow at Rf. A = 7.
- All macro inputs hard-capped at 2024-12-31. Tolerance between Python/LLM and Excel: absolute difference <= 0.005 (0.5 percentage points) on return and st. dev.; internal target <= 0.0001.
- Commit by explicit path only (`git add <files>`), never `git add -A`. Commit messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Excel formulas: no hardcoded results in Sheets 6, 7, 8. Use `Workbook(..., {"use_future_functions": True})` so `STDEV.S` and `COVARIANCE.S` get the `_xlfn.` prefix automatically.
- Sheet names: `Cover`, `S1_Summary`, `S2_MVF_Excel`, `S3_MVF_AI`, `S4_Prices`, `S5_Macro`, `S6_Returns`, `S7_Cov`, `S8_Solver`.

## Review Focus

1. ORP collapsing to a single ETF (or two with one near zero): must raise, not silently pass. Tested in Task 2.
2. Local optimum or Solver/SLSQP disagreement: multi-start SLSQP; reconciliation against the user's Solver run. Tasks 2 and 8.
3. Look-ahead leakage in the macro model (data after 2024-12-31, or CPI/unemployment used before publication). Tested in Tasks 1 and 4.
4. Yahoo returning a partial current month or retroactively changed adjusted closes: trim to Dec 2025 and cache a snapshot. Tested in Task 1.
5. OCP with y > 1 (borrowing) giving a negative cash position in Step 8. Tested in Tasks 2 and 3.
6. RF unit errors (percent vs decimal). Tested in Task 1.

## Rubric Coverage Map

| Rubric criterion | Where it is met | Beyond-excellent extra |
|---|---|---|
| Data accuracy and organisation | Tasks 1, 6, 7 (all 9 sheets, live formulas, consistent formatting) | Data-quality log, colour legend, README block on the cover sheet |
| Portfolio optimisation using Solver | Tasks 2, 7, 8 (pre-wired Sheet 8, reconciliation) | Closed-form OCP check cell, Python vs Solver table |
| AI-generated outputs match Excel | Tasks 9, 10 | Discrepancy log with root causes, repeat-run variability test |
| Charts and visualisation | Task 7 (native chart, labels, CAL) and Task 9 (AI chart) | Individual ETFs plotted, ORP/OCP annotated with weights |
| Documentation (prompts) | Tasks 9, 10, 11 | Version history with screenshot slots, fresh-chat reproduction check |
| Forward-looking AI portfolio | Tasks 4, 10, 11 | Leakage guards, CV diagnostics, coefficient table, justification prompt |
| Portfolio comparison | Task 3 | Sharpe, Sortino, Treynor, Jensen alpha, M2, max drawdown, information ratio |
| Evaluation of AI | Tasks 5, 11 | Quantified fragility from Ledoit-Wolf, perturbation and bootstrap |
| Consulting pitch, live demo, Q&A, teamwork (group) | Task 12 | Demo runbook, fallback outputs, Q&A cheat sheet for the group |

---

### Task 1: Scaffolding, config and data layer (DONE, committed)

**Files:** `requirements.txt`, `pytest.ini`, `config.py`, `data.py`, `tests/test_data.py`, `data/*.csv`

**Interfaces:**
- Produces: `config.ALL: list[str]`, `config.EQUITY`, `config.BONDS`, `config.ALT`, `config.A: int`, `config.MACRO_CAP: str`, `config.EST_START/EST_END/HOLD_START/HOLD_END`
- Produces: `data.load_prices() -> tuple[DataFrame, DataFrame]` (adj close, close; month-end index, columns `ALL`, 61 rows Dec 2020 to Dec 2025)
- Produces: `data.load_french() -> DataFrame` (month-end index; columns `Mkt-RF, SMB, HML, RF` in percent as published)
- Produces: `data.rf_decimal(ff) -> Series` (monthly decimal RF)
- Produces: `data.load_macro() -> DataFrame` (month-end index 2019-01 to 2024-12; columns `DGS10, T10Y2Y, VIXCLS, FEDFUNDS, CPIAUCSL, UNRATE`)

Tests: `.venv/bin/pytest tests/test_data.py -q` → 3 passed.

---

### Task 2: Statistics and optimiser (MVP, ORP, OCP, frontier)

**Files:**
- Create: `optimize.py`, `tests/test_optimize.py`

**Interfaces:**
- Consumes: `data.load_prices`, `data.load_french`, `data.rf_decimal`, `config.EST_START/EST_END`
- Produces: `optimize.monthly_returns(adj) -> DataFrame`
- Produces: `optimize.annual_stats(r, rf_m) -> tuple[DataFrame(ret, sd, sharpe), float rf_annual]`
- Produces: `optimize.annual_cov(r) -> DataFrame`
- Produces: `optimize.mvp(S) -> ndarray`, `optimize.orp(mu, S, rf) -> ndarray` (raises `ORPConcentrationError`), `optimize.ocp(w_orp, mu, S, rf, A) -> dict(y, w_risky, w_rf, ret, sd, utility)`
- Produces: `optimize.frontier(mu, S, n=80) -> DataFrame(ret, sd, 0..9)`, `optimize.port_stats(w, mu, S) -> tuple[float, float]`
- Produces: `optimize.estimation_inputs() -> tuple[r_est, rf_m_est, stats(DataFrame ret/sd/sharpe), S(DataFrame), rf(float)]`

- [ ] **Step 1: Write the failing tests `tests/test_optimize.py`**

```python
import numpy as np
import pandas as pd
import pytest
from optimize import (mvp, orp, ocp, frontier, port_stats, ORPConcentrationError,
                      estimation_inputs)


def test_mvp_two_uncorrelated_assets_matches_analytic():
    S = np.array([[0.04, 0.0], [0.0, 0.01]])
    assert np.allclose(mvp(S), [0.2, 0.8], atol=1e-5)


def test_orp_is_long_only_fully_invested_and_beats_every_single_asset():
    r, rf_m, st, S, rf = estimation_inputs()
    mu = st["ret"].values
    w = orp(mu, S.values, rf)
    assert w.min() >= 0 and abs(w.sum() - 1) < 1e-8
    ret, sd = port_stats(w, mu, S.values)
    assert (ret - rf) / sd >= st["sharpe"].max() - 1e-9


def test_orp_raises_when_it_would_hold_one_etf():
    mu = np.array([0.30, 0.01]); S = np.array([[0.01, 0.0], [0.0, 0.04]])
    with pytest.raises(ORPConcentrationError):
        orp(mu, S, rf=0.0)  # asset 1 dominates; ORP = 100% asset 1


def test_ocp_matches_closed_form_and_allows_borrowing():
    mu = np.array([0.20, 0.10]); S = np.array([[0.02, 0.0], [0.0, 0.02]])
    w = np.array([0.7, 0.3]); rf = 0.02
    out = ocp(w, mu, S, rf, A=7)
    ret_p, sd_p = port_stats(w, mu, S)
    assert out["y"] == pytest.approx((ret_p - rf) / (7 * sd_p**2))
    out2 = ocp(w, mu, S, rf, A=1)           # low risk aversion -> y > 1 -> borrow
    assert out2["y"] > 1 and out2["w_rf"] < 0
    assert out2["w_risky"].sum() + out2["w_rf"] == pytest.approx(1)


def test_frontier_never_below_mvp_variance_and_long_only():
    r, rf_m, st, S, rf = estimation_inputs()
    f = frontier(st["ret"].values, S.values, n=40)
    sd_mvp = port_stats(mvp(S.values), st["ret"].values, S.values)[1]
    assert (f["sd"] >= sd_mvp - 1e-6).all()


def test_real_data_orp_has_at_least_two_etfs():
    r, rf_m, st, S, rf = estimation_inputs()
    w = orp(st["ret"].values, S.values, rf)
    assert (w > 1e-4).sum() >= 2
    assert len(r) == 48
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_optimize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'optimize'`

- [ ] **Step 3: Write `optimize.py`**

```python
import numpy as np
import pandas as pd
from scipy.optimize import minimize

from config import EST_END, EST_START, A as RISK_AVERSION
from data import load_french, load_prices, rf_decimal

MIN_ACTIVE = 1e-4


class ORPConcentrationError(ValueError):
    pass


def monthly_returns(adj):
    return adj.pct_change().dropna()


def annual_stats(r, rf_m):
    mu = r.mean() * 12
    sd = r.std(ddof=1) * np.sqrt(12)
    rf = float(rf_m.mean() * 12)
    return pd.DataFrame({"ret": mu, "sd": sd, "sharpe": (mu - rf) / sd}), rf


def annual_cov(r):
    return r.cov() * 12          # ddof=1, same as Excel COVARIANCE.S


def estimation_inputs():
    adj, _ = load_prices()
    r = monthly_returns(adj)[EST_START:EST_END]
    rf_m = rf_decimal(load_french())[EST_START:EST_END]
    st, rf = annual_stats(r, rf_m)
    return r, rf_m, st, annual_cov(r), rf


def port_stats(w, mu, S):
    w = np.asarray(w)
    return float(w @ mu), float(np.sqrt(w @ S @ w))


def _solve(fun, n, extra=()):
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1}, *extra]
    starts = [np.ones(n) / n] + [np.random.default_rng(s).dirichlet(np.ones(n)) for s in range(8)]
    best = None
    for x0 in starts:
        res = minimize(fun, x0, method="SLSQP", bounds=[(0, 1)] * n, constraints=cons,
                       options={"ftol": 1e-13, "maxiter": 2000})
        if res.success and (best is None or res.fun < best.fun):
            best = res
    if best is None:
        raise RuntimeError("optimiser failed from all starts")
    w = np.where(best.x < 1e-8, 0.0, best.x)
    return w / w.sum()


def mvp(S):
    S = np.asarray(S)
    return _solve(lambda w: w @ S @ w, len(S))


def orp(mu, S, rf):
    mu, S = np.asarray(mu), np.asarray(S)
    w = _solve(lambda w: -(w @ mu - rf) / np.sqrt(w @ S @ w), len(mu))
    if (w > MIN_ACTIVE).sum() < 2:
        raise ORPConcentrationError(
            f"ORP holds {(w > MIN_ACTIVE).sum()} ETF(s); brief requires >= 2. Choose other ETFs.")
    return w


def ocp(w_orp, mu, S, rf, A=RISK_AVERSION):
    mu, S, w = np.asarray(mu), np.asarray(S), np.asarray(w_orp)
    ret_p, sd_p = port_stats(w, mu, S)
    y = (ret_p - rf) / (A * sd_p**2)
    ret = rf + y * (ret_p - rf)
    sd = y * sd_p
    return {"y": y, "w_risky": y * w, "w_rf": 1 - y, "ret": ret, "sd": sd,
            "utility": ret - 0.5 * A * sd**2}


def frontier(mu, S, n=80):
    mu, S = np.asarray(mu), np.asarray(S)
    rows = []
    for t in np.linspace(mu.min(), mu.max(), n):
        w = _solve(lambda w: w @ S @ w, len(mu),
                   extra=[{"type": "eq", "fun": lambda w, t=t: w @ mu - t}])
        rows.append((t, np.sqrt(w @ S @ w), *w))
    return pd.DataFrame(rows, columns=["ret", "sd", *range(len(mu))])
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_optimize.py -v`
Expected: 6 PASS. If `test_orp_raises_when_it_would_hold_one_etf` fails because SLSQP leaves 1e-9 dust, it is handled by the 1e-8 floor in `_solve`; do not loosen `MIN_ACTIVE`.

- [ ] **Step 5: Print the headline numbers for the record**

```bash
.venv/bin/python -c "
from optimize import *
r,rf_m,st,S,rf=estimation_inputs(); mu=st['ret'].values
w=orp(mu,S.values,rf); print(st.round(4)); print('rf',rf)
print('ORP',dict(zip(S.columns,w.round(4)))); print('MVP',dict(zip(S.columns,mvp(S.values).round(4))))
print(ocp(w,mu,S.values,rf))" | tee docs/results_step4.txt
```
Expected: ORP near GLD 0.39 / XLE 0.38 / QQQ 0.23 (dry-run values).

- [ ] **Step 6: Commit**

```bash
git add optimize.py tests/test_optimize.py docs/results_step4.txt
git commit -m "feat: optimiser (MVP, ORP with >=2 ETF guard, OCP, frontier)"
```

---

### Task 3: Step 8 evaluation (wealth path and performance metrics)

**Files:**
- Create: `evaluate.py`, `tests/test_evaluate.py`

**Interfaces:**
- Consumes: `optimize.ocp` result dict (`w_risky: ndarray`, `w_rf: float`), `data.load_prices/load_french`, `optimize.monthly_returns`
- Produces: `evaluate.holdout_inputs() -> tuple[r25 DataFrame, rf25 Series]`
- Produces: `evaluate.wealth(w_risky, w_rf, r, rf_m, start=100_000, rebalance=False) -> Series` (index: start date + 12 month-ends)
- Produces: `evaluate.metrics(wealth, rf_m, mkt_ret) -> dict` with keys `end_value, total_return, ann_ret, ann_sd, sharpe, sortino, max_drawdown, beta, jensen_alpha, treynor, m2, info_ratio`

- [ ] **Step 1: Write the failing tests `tests/test_evaluate.py`**

```python
import numpy as np
import pandas as pd
import pytest
from evaluate import wealth, metrics


def _toy():
    idx = pd.date_range("2025-01-31", periods=3, freq="ME")
    r = pd.DataFrame({"A": [0.10, 0.00, -0.05], "B": [0.00, 0.02, 0.02]}, index=idx)
    rf = pd.Series([0.003] * 3, index=idx)
    return r, rf


def test_buy_and_hold_all_in_one_asset():
    r, rf = _toy()
    w = wealth(np.array([1.0, 0.0]), 0.0, r, rf, start=100.0)
    assert w.iloc[-1] == pytest.approx(100 * 1.10 * 1.00 * 0.95)
    assert len(w) == 4


def test_leveraged_position_borrows_at_rf():
    r, rf = _toy()
    w = wealth(np.array([1.5, 0.0]), -0.5, r, rf, start=100.0)
    expected = 100 * (1.5 * 1.10 * 1.0 * 0.95 - 0.5 * (1.003 ** 3))
    assert w.iloc[-1] == pytest.approx(expected)


def test_rebalanced_differs_from_buy_and_hold():
    r, rf = _toy()
    a = wealth(np.array([0.5, 0.5]), 0.0, r, rf, 100.0, rebalance=False).iloc[-1]
    b = wealth(np.array([0.5, 0.5]), 0.0, r, rf, 100.0, rebalance=True).iloc[-1]
    assert a != pytest.approx(b)


def test_metrics_keys_and_drawdown():
    r, rf = _toy()
    w = wealth(np.array([1.0, 0.0]), 0.0, r, rf, 100.0)
    m = metrics(w, rf, r["B"])
    assert m["max_drawdown"] == pytest.approx(-0.05)
    for k in ["end_value", "sharpe", "sortino", "beta", "jensen_alpha", "treynor", "m2", "info_ratio"]:
        assert k in m
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_evaluate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'evaluate'`

- [ ] **Step 3: Write `evaluate.py`**

```python
import numpy as np
import pandas as pd

from config import HOLD_END, HOLD_START
from data import load_french, load_prices, rf_decimal
from optimize import monthly_returns


def holdout_inputs():
    adj, _ = load_prices()
    r = monthly_returns(adj)[HOLD_START:HOLD_END]
    rf = rf_decimal(load_french())[HOLD_START:HOLD_END]
    return r, rf


def wealth(w_risky, w_rf, r, rf_m, start=100_000.0, rebalance=False):
    w = np.asarray(w_risky, float)
    if rebalance:
        rp = r.values @ w + w_rf * rf_m.values
        path = start * np.cumprod(1 + rp)
    else:  # buy and hold: each sleeve compounds on its own; cash/borrowing at rf
        risky = (w * np.cumprod(1 + r.values, axis=0)).sum(axis=1)
        cash = w_rf * np.cumprod(1 + rf_m.values)
        path = start * (risky + cash)
    first = r.index[0] - pd.offsets.MonthEnd(1)
    return pd.Series(np.r_[start, path], index=[first, *r.index])


def metrics(wealth_path, rf_m, mkt_ret):
    R = wealth_path.pct_change().dropna()
    ex = R - rf_m.values
    mx = mkt_ret.values - rf_m.values
    sd = R.std(ddof=1) * np.sqrt(12)
    ann_ret = R.mean() * 12
    rf_a = rf_m.mean() * 12
    sharpe = (ex.mean() * 12) / sd
    downside = np.sqrt((np.minimum(ex, 0) ** 2).mean()) * np.sqrt(12)
    cov = np.cov(ex, mx, ddof=1)
    beta = cov[0, 1] / cov[1, 1]
    alpha = (ex.mean() - beta * mx.mean()) * 12
    mkt_sd = mkt_ret.std(ddof=1) * np.sqrt(12)
    active = R.values - mkt_ret.values
    return {
        "end_value": float(wealth_path.iloc[-1]),
        "total_return": float(wealth_path.iloc[-1] / wealth_path.iloc[0] - 1),
        "ann_ret": float(ann_ret), "ann_sd": float(sd), "sharpe": float(sharpe),
        "sortino": float(ex.mean() * 12 / downside) if downside > 0 else float("nan"),
        "max_drawdown": float((wealth_path / wealth_path.cummax() - 1).min()),
        "beta": float(beta), "jensen_alpha": float(alpha),
        "treynor": float(ex.mean() * 12 / beta) if beta != 0 else float("nan"),
        "m2": float(sharpe * mkt_sd + rf_a),
        "info_ratio": float(active.mean() * 12 / (active.std(ddof=1) * np.sqrt(12))),
    }
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_evaluate.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add evaluate.py tests/test_evaluate.py
git commit -m "feat: Step 8 wealth path and performance metrics"
```

---

### Task 4: Forward-looking macro model (Step 6)

**Files:**
- Create: `forward_model.py`, `tests/test_forward_model.py`

**Interfaces:**
- Consumes: `data.load_macro`, `optimize.estimation_inputs`, `optimize.orp`, `optimize.ocp`
- Produces: `forward_model.build_features(m: DataFrame) -> DataFrame` (columns `y10, curve, vix, ffr, cpi_yoy, unrate`; CPI and unemployment lagged one extra month for publication delay)
- Produces: `forward_model.fit_forward(r_est, feats) -> dict(mu_fwd: Series (annualised), alpha: Series, coefs: DataFrame, loo_r2: Series)`
- Produces: `forward_model.forward_ocp() -> dict` with `w_orp, ocp, mu_fwd, S_lw, diagnostics, rf`

- [ ] **Step 1: Write the failing tests `tests/test_forward_model.py`**

```python
import numpy as np
import pandas as pd
from data import load_macro
from forward_model import build_features, fit_forward, forward_ocp
from optimize import estimation_inputs


def test_features_use_no_data_after_cap_and_lag_cpi():
    m = load_macro()
    f = build_features(m)
    assert f.index.max() <= pd.Timestamp("2024-12-31")
    cpi_yoy_raw = m["CPIAUCSL"].pct_change(12) * 100
    # published-with-delay: Dec-2024 feature equals Nov-2024 raw CPI YoY
    assert np.isclose(f.loc["2024-12-31", "cpi_yoy"], cpi_yoy_raw.loc["2024-11-30"])


def test_fit_uses_only_prior_month_features():
    r, *_ = estimation_inputs()
    f = build_features(load_macro())
    out = fit_forward(r, f)
    assert set(out["mu_fwd"].index) == set(r.columns)
    assert out["loo_r2"].notna().all()


def test_forward_ocp_is_valid_and_has_two_plus_etfs():
    out = forward_ocp()
    assert abs(out["w_orp"].sum() - 1) < 1e-8 and out["w_orp"].min() >= 0
    assert (out["w_orp"] > 1e-4).sum() >= 2
    assert out["ocp"]["y"] > 0
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_forward_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'forward_model'`

- [ ] **Step 3: Write `forward_model.py`**

```python
import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf
from sklearn.linear_model import Ridge, RidgeCV
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.preprocessing import StandardScaler

from config import A, MACRO_CAP
from data import load_macro
from optimize import estimation_inputs, ocp, orp

PUB_LAG = {"cpi_yoy": 1, "unrate": 1}   # CPI / unemployment are published ~1 month late


def build_features(m):
    f = pd.DataFrame({
        "y10": m["DGS10"], "curve": m["T10Y2Y"], "vix": m["VIXCLS"], "ffr": m["FEDFUNDS"],
        "cpi_yoy": m["CPIAUCSL"].pct_change(12) * 100, "unrate": m["UNRATE"]})
    for c, lag in PUB_LAG.items():
        f[c] = f[c].shift(lag)
    return f[f.index <= pd.Timestamp(MACRO_CAP)]


def fit_forward(r_est, feats):
    X = feats.shift(1).reindex(r_est.index)        # info known at t-1 predicts return at t
    assert not X.isna().any().any(), "missing macro features in estimation window"
    sc = StandardScaler().fit(X)
    Xs = sc.transform(X)
    rcv = RidgeCV(alphas=np.logspace(-1, 3, 40), alpha_per_target=True).fit(Xs, r_est.values)
    alphas = pd.Series(rcv.alpha_, index=r_est.columns)
    loo = {}
    for t in r_est.columns:
        pred = cross_val_predict(Ridge(alpha=alphas[t]), Xs, r_est[t].values, cv=LeaveOneOut())
        loo[t] = 1 - ((r_est[t].values - pred) ** 2).sum() / ((r_est[t].values - r_est[t].mean()) ** 2).sum()
    x_now = sc.transform(feats.loc[[pd.Timestamp(MACRO_CAP)]])   # Dec-2024 state -> 2025
    mu_fwd = pd.Series(rcv.predict(x_now)[0] * 12, index=r_est.columns)
    coefs = pd.DataFrame(rcv.coef_.T, index=X.columns, columns=r_est.columns)
    return {"mu_fwd": mu_fwd, "alpha": alphas, "coefs": coefs, "loo_r2": pd.Series(loo)}


def forward_ocp():
    r, rf_m, st, S_sample, rf = estimation_inputs()
    fit = fit_forward(r, build_features(load_macro()))
    S_lw = pd.DataFrame(LedoitWolf().fit(r.values).covariance_ * 12,
                        index=r.columns, columns=r.columns)
    w = orp(fit["mu_fwd"].values, S_lw.values, rf)
    return {"w_orp": w, "ocp": ocp(w, fit["mu_fwd"].values, S_lw.values, rf, A),
            "mu_fwd": fit["mu_fwd"], "S_lw": S_lw, "diagnostics": fit, "rf": rf}
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_forward_model.py -v`
Expected: 3 PASS. If `ORPConcentrationError` is raised, the forward ORP is too concentrated: raise the lower bound of `np.logspace(-1, 3, 40)` to 1 (stronger shrinkage), record the change and why in `docs/results_step6.txt`; do not weaken the 2-ETF rule.

- [ ] **Step 5: Save diagnostics for the write-up**

```bash
.venv/bin/python -c "
from forward_model import forward_ocp
o=forward_ocp(); d=o['diagnostics']
print(d['mu_fwd'].round(4)); print(d['alpha']); print(d['loo_r2'].round(3)); print(d['coefs'].round(4))
print(dict(zip(o['mu_fwd'].index,o['w_orp'].round(4)))); print({k:v for k,v in o['ocp'].items()})
" | tee docs/results_step6.txt
```

- [ ] **Step 6: Commit**

```bash
git add forward_model.py tests/test_forward_model.py docs/results_step6.txt
git commit -m "feat: macro ridge forward model with leakage guards"
```

---

### Task 5: Robustness (Ledoit-Wolf, perturbation, bootstrap)

**Files:**
- Create: `robustness.py`, `tests/test_robustness.py`

**Interfaces:**
- Consumes: `optimize.mvp/orp/ocp/estimation_inputs/annual_stats/annual_cov/_solve/ORPConcentrationError`
- Produces: `robustness.lw_cov(r) -> DataFrame` (annualised)
- Produces: `robustness.perturb_cov(S, scale, rng) -> ndarray` (symmetric, positive definite)
- Produces: `robustness.sensitivity(r, rf_m, n=300, scale=0.10, seed=0, mode="perturb"|"bootstrap") -> dict(weights: dict[str, DataFrame], summary: DataFrame, frac_orp_lt2: float)`
- Produces: `robustness.compare_lw() -> DataFrame` (columns `MVP_sample, MVP_LW, ORP_sample, ORP_LW, OCP_sample, OCP_LW`)

- [ ] **Step 1: Write the failing tests `tests/test_robustness.py`**

```python
import numpy as np
from optimize import estimation_inputs
from robustness import lw_cov, perturb_cov, sensitivity, compare_lw


def test_perturbed_cov_is_symmetric_positive_definite():
    r, rf_m, st, S, rf = estimation_inputs()
    P = perturb_cov(S.values, 0.10, np.random.default_rng(1))
    assert np.allclose(P, P.T)
    assert np.linalg.eigvalsh(P).min() > 0


def test_lw_shrinks_offdiagonals_toward_zero_magnitude():
    r, *_ = estimation_inputs()
    S = r.cov().values * 12
    L = lw_cov(r).values
    assert np.abs(L - np.diag(np.diag(L))).sum() <= np.abs(S - np.diag(np.diag(S))).sum()


def test_sensitivity_reports_weight_spread_and_orp_failures():
    r, rf_m, *_ = estimation_inputs()
    out = sensitivity(r, rf_m, n=30, scale=0.10, seed=0, mode="perturb")
    assert set(out["weights"]) == {"MVP", "ORP", "OCP"}
    assert out["weights"]["ORP"].shape == (30, 10)
    assert 0 <= out["frac_orp_lt2"] <= 1
    assert {"mean", "std", "p05", "p95"} <= set(out["summary"].columns.get_level_values(1))


def test_compare_lw_has_both_covariances():
    t = compare_lw()
    assert {"MVP_sample", "MVP_LW", "ORP_sample", "ORP_LW"} <= set(t.columns)
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_robustness.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'robustness'`

- [ ] **Step 3: Write `robustness.py`**

```python
import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

from config import A
from optimize import (ORPConcentrationError, _solve, annual_cov, annual_stats,
                      estimation_inputs, mvp, ocp, orp)


def lw_cov(r):
    return pd.DataFrame(LedoitWolf().fit(r.values).covariance_ * 12,
                        index=r.columns, columns=r.columns)


def perturb_cov(S, scale, rng):
    E = rng.normal(0, scale, S.shape)
    P = S * (1 + (E + E.T) / 2)
    vals, vecs = np.linalg.eigh((P + P.T) / 2)
    return (vecs * np.clip(vals, 1e-8, None)) @ vecs.T


def sensitivity(r, rf_m, n=300, scale=0.10, seed=0, mode="perturb"):
    rng = np.random.default_rng(seed)
    st, rf = annual_stats(r, rf_m)
    mu0, S0 = st["ret"].values, annual_cov(r).values
    rows = {"MVP": [], "ORP": [], "OCP": []}
    lt2 = 0
    for _ in range(n):
        if mode == "bootstrap":
            idx = rng.integers(0, len(r), len(r))
            rb, rfb = r.iloc[idx], rf_m.iloc[idx]
            stb, rf_i = annual_stats(rb, rfb)
            mu, S = stb["ret"].values, annual_cov(rb).values
        else:
            mu, S, rf_i = mu0, perturb_cov(S0, scale, rng), rf
        w_mvp = mvp(S)
        try:
            w_orp = orp(mu, S, rf_i)
        except ORPConcentrationError:
            lt2 += 1   # keep the concentrated solution so spread statistics stay honest
            w_orp = _solve(lambda w: -(w @ mu - rf_i) / np.sqrt(w @ S @ w), len(mu))
        rows["MVP"].append(w_mvp); rows["ORP"].append(w_orp)
        rows["OCP"].append(ocp(w_orp, mu, S, rf_i, A)["w_risky"])
    cols = list(r.columns)
    weights = {k: pd.DataFrame(v, columns=cols) for k, v in rows.items()}
    summary = pd.concat(
        {k: pd.DataFrame({"mean": v.mean(), "std": v.std(),
                          "p05": v.quantile(.05), "p95": v.quantile(.95)})
         for k, v in weights.items()}, axis=1)
    return {"weights": weights, "summary": summary, "frac_orp_lt2": lt2 / n}


def compare_lw():
    r, rf_m, st, S, rf = estimation_inputs()
    mu = st["ret"].values
    L = lw_cov(r)
    out = pd.DataFrame(index=r.columns)
    for tag, cov in (("sample", S), ("LW", L)):
        w_o = orp(mu, cov.values, rf)
        out[f"MVP_{tag}"] = mvp(cov.values)
        out[f"ORP_{tag}"] = w_o
        out[f"OCP_{tag}"] = ocp(w_o, mu, cov.values, rf, A)["w_risky"]
    return out
```

(`summary` has a two-level column index: portfolio (`MVP/ORP/OCP`) over statistic (`mean/std/p05/p95`), which is what the test reads.)

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_robustness.py -v`
Expected: 4 PASS

- [ ] **Step 5: Generate the headline numbers for the write-up**

```bash
.venv/bin/python -c "
from optimize import estimation_inputs
from robustness import sensitivity, compare_lw
import pandas as pd; pd.set_option('display.width',200)
print(compare_lw().round(3))
r,rf_m,*_=estimation_inputs()
for mode,sc in (('perturb',0.05),('perturb',0.10),('bootstrap',0)):
    o=sensitivity(r,rf_m,n=300,scale=sc,mode=mode); print(mode,sc,'frac ORP<2:',o['frac_orp_lt2']); print(o['summary']['ORP'].round(3))
" | tee docs/results_robustness.txt
```

- [ ] **Step 6: Commit**

```bash
git add robustness.py tests/test_robustness.py docs/results_robustness.txt
git commit -m "feat: Ledoit-Wolf, covariance perturbation and bootstrap sensitivity"
```

---

### Task 6: Workbook data and formula sheets (Cover, S4, S5, S6, S7)

**Files:**
- Create: `build_workbook.py` (first part), `tests/test_workbook_structure.py`

**Interfaces:**
- Consumes: `data.load_prices/load_french/load_macro`, `config.ALL`
- Produces: `build_workbook.build(path: str) -> None` (writes all sheets; later tasks extend `build`)
- Produces cell map (fixed, relied on by Tasks 7-8): `S4_Prices` row 1 headers, rows 2-62 Dec 2020 to Dec 2025, adj close in `B:K`, close in `N:W`; `S5_Macro` French block `A:E` (Date, Mkt-RF, SMB, HML, RF in percent) rows 2-62, macro block from column `H`; `S6_Returns` rows 2-61 returns (Jan 2021 to Dec 2025) in `B:K`, RF decimal in `L`; rows 2-49 are the estimation window; stats rows 64 (ann. return), 65 (ann. sd), 66 (rf annual, in `B66`), 67 (Sharpe); `S7_Cov!B2:K11` annualised covariance, labels in row 1 and column A.

- [ ] **Step 1: Write the failing structural test `tests/test_workbook_structure.py`**

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_workbook_structure.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'build_workbook'`

- [ ] **Step 3: Write `build_workbook.py` (data and formula sheets)**

Create all nine worksheets up front in order and pass the handles to the writers, so Task 7 can fill the stub sheets without re-adding them.

```python
import xlsxwriter
from xlsxwriter.utility import xl_col_to_name as col

from config import ALL, A
from data import load_french, load_macro, load_prices

N = len(ALL)  # 10
SHEETS = ["Cover", "S1_Summary", "S2_MVF_Excel", "S3_MVF_AI", "S4_Prices",
          "S5_Macro", "S6_Returns", "S7_Cov", "S8_Solver"]


def _formats(wb):
    return {
        "hdr": wb.add_format({"bold": True, "bg_color": "#1F3864", "font_color": "white", "align": "center"}),
        "date": wb.add_format({"num_format": "mmm-yyyy"}),
        "px": wb.add_format({"num_format": "0.00"}),
        "pct": wb.add_format({"num_format": "0.00%"}),
        "pct4": wb.add_format({"num_format": "0.0000%"}),
        "num": wb.add_format({"num_format": "0.0000"}),
        "inp": wb.add_format({"num_format": "0.0000", "bg_color": "#FFF2CC", "border": 1}),
        "bold": wb.add_format({"bold": True}),
        "title": wb.add_format({"bold": True, "font_size": 14}),
    }


def write_prices(ws, f):
    adj, close = load_prices()
    ws.write(0, 0, "Date", f["hdr"])
    for j, t in enumerate(ALL):
        ws.write(0, 1 + j, t, f["hdr"]); ws.write(0, 13 + j, t, f["hdr"])
    ws.write(0, 12, "Close ->", f["bold"])
    for i, d in enumerate(adj.index):
        ws.write_datetime(1 + i, 0, d.to_pydatetime(), f["date"])
        for j, t in enumerate(ALL):
            ws.write_number(1 + i, 1 + j, float(adj.iloc[i, j]), f["px"])
            ws.write_number(1 + i, 13 + j, float(close.iloc[i, j]), f["px"])
    ws.write(63, 0, "Source: Yahoo Finance via yfinance, month-end Adj Close (cols B:K) and Close (cols N:W).", f["bold"])
    ws.freeze_panes(1, 1)


def write_macro(ws, f):
    ff, m = load_french(), load_macro()
    ff = ff["2020-12-31":"2025-12-31"]
    for j, h in enumerate(["Date", "Mkt-RF (%)", "SMB (%)", "HML (%)", "RF (%)"]):
        ws.write(0, j, h, f["hdr"])
    for i, (d, row) in enumerate(ff.iterrows()):
        ws.write_datetime(1 + i, 0, d.to_pydatetime(), f["date"])
        for j, v in enumerate(row.values):
            ws.write_number(1 + i, 1 + j, float(v), f["num"])
    ws.write(len(ff) + 2, 0, "Source: Kenneth French Data Library, F-F_Research_Data_Factors (monthly), percent.", f["bold"])
    ws.write(0, 7, "Date", f["hdr"])
    for j, c in enumerate(m.columns):
        ws.write(0, 8 + j, c, f["hdr"])
    for i, (d, row) in enumerate(m.iterrows()):
        ws.write_datetime(1 + i, 7, d.to_pydatetime(), f["date"])
        for j, v in enumerate(row.values):
            if v == v:
                ws.write_number(1 + i, 8 + j, float(v), f["num"])
    ws.write(len(m) + 2, 7, "Source: FRED (daily series averaged to month); capped at 2024-12-31 for the Step 6 model.", f["bold"])


def write_returns(ws, f):
    ws.write(0, 0, "Date", f["hdr"])
    for j, t in enumerate(ALL):
        ws.write(0, 1 + j, t, f["hdr"])
    ws.write(0, 11, "RF (monthly)", f["hdr"])
    adj, _ = load_prices()
    for i in range(60):                      # Jan 2021 .. Dec 2025 -> sheet rows 2..61
        r = i + 2                            # excel row of this return
        ws.write_datetime(i + 1, 0, adj.index[i + 1].to_pydatetime(), f["date"])
        for j in range(N):
            c = col(1 + j)
            ws.write_formula(i + 1, 1 + j, f"=S4_Prices!{c}{r + 1}/S4_Prices!{c}{r}-1", f["pct"])
        ws.write_formula(i + 1, 11, f"=S5_Macro!E{r + 1}/100", f["pct4"])
    labels = {63: "Annualised return (arith. mean x 12)", 64: "Annualised st. dev. (STDEV.S x SQRT 12)",
              65: "Risk-free (annual, mean monthly RF x 12)", 66: "Sharpe ratio"}
    for row, text in labels.items():
        ws.write(row, 0, text, f["bold"])
    for j in range(N):
        c = col(1 + j)
        ws.write_formula(63, 1 + j, f"=AVERAGE({c}2:{c}49)*12", f["pct"])
        ws.write_formula(64, 1 + j, f"=STDEV.S({c}2:{c}49)*SQRT(12)", f["pct"])
        ws.write_formula(66, 1 + j, f"=({c}64-$B$66)/{c}65", f["num"])
    ws.write_formula(65, 1, "=AVERAGE(L2:L49)*12", f["pct4"])
    ws.write(68, 0, "Estimation window: rows 2-49 (Jan 2021 - Dec 2024, 48 obs). Rows 50-61 (2025) are hold-out, used only in Step 8.", f["bold"])
    ws.freeze_panes(1, 1)


def write_cov(ws, f):
    ws.write(0, 0, "Annualised cov (monthly COVARIANCE.S x 12)", f["hdr"])
    for j, t in enumerate(ALL):
        ws.write(0, 1 + j, t, f["hdr"]); ws.write(1 + j, 0, t, f["hdr"])
    rng = "S6_Returns!$B$2:$K$49"
    for i in range(N):
        for j in range(N):
            ws.write_formula(1 + i, 1 + j,
                f"=COVARIANCE.S(INDEX({rng},0,ROW()-1),INDEX({rng},0,COLUMN()-1))*12", f["num"])


def build(path):
    wb = xlsxwriter.Workbook(path, {"use_future_functions": True})
    f = _formats(wb)
    ws = {name: wb.add_worksheet(name) for name in SHEETS}   # creation order fixes sheet order
    write_prices(ws["S4_Prices"], f); write_macro(ws["S5_Macro"], f)
    write_returns(ws["S6_Returns"], f); write_cov(ws["S7_Cov"], f)
    wb.close()


if __name__ == "__main__":
    build("FIN3702B_Portfolio.xlsx")
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_workbook_structure.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add build_workbook.py tests/test_workbook_structure.py
git commit -m "feat: workbook data, returns and covariance sheets with live formulas"
```

---

### Task 7: Solver sheet (S8), native MVF chart (S2), Summary (S1), Cover

**Files:**
- Modify: `build_workbook.py` (add `write_solver`, `write_mvf_chart`, `write_summary`, `write_cover`, and call them from `build`)
- Modify: `tests/test_workbook_structure.py` (add tests below)

**Interfaces:**
- Consumes: Task 6 cell map; `optimize.mvp/orp/ocp/frontier/estimation_inputs`; `forward_model.forward_ocp`; `evaluate.*`
- Produces `S8_Solver` cell map: tickers `B3:K3`; E[r] `B4:K4`; sigma `B5:K5`; rf `B6`; MVP weights `B9:K9` (sum `L9`), return `B10`, variance `B11`, sd `B12`; ORP weights `B15:K15` (sum `L15`), return `B16`, variance `B17`, sd `B18`, Sharpe `B19`, active count `B20`; OCP: y `B23`, risky weights `B24:K24`, rf weight `B25`, return `B26`, sd `B27`, utility `B28`, A `B29`, closed-form y check `B30`.

- [ ] **Step 1: Add failing tests**

```python
def test_solver_sheet_layout_and_formulas(wb):
    s = wb["S8_Solver"]
    assert str(s["B11"].value).startswith("=SUMPRODUCT(MMULT(B9:K9")
    assert "COUNTIF" in s["B20"].value and str(s["B19"].value).startswith("=")
    assert s["B29"].value == 7
    assert "B23*B15" in s["B24"].value.replace("$", "")


def test_chart_and_summary_exist(tmp_path_factory):
    import zipfile
    p = tmp_path_factory.mktemp("c") / "c.xlsx"
    build(str(p))
    assert any(n.startswith("xl/charts/chart") for n in zipfile.ZipFile(p).namelist())
    s1 = openpyxl.load_workbook(p)["S1_Summary"]
    assert str(s1["B12"].value).startswith("=")        # portfolio return is a formula
```

Run: `.venv/bin/pytest tests/test_workbook_structure.py -v`. Expected: the two new tests FAIL.

- [ ] **Step 2: Implement `write_solver`**

Layout per the cell map. Weight cells (`B9:K9`, `B15:K15`, `B23`) get the yellow `inp` format and are pre-filled with the Python solutions (`mvp(S)`, `orp(mu,S,rf)`, `ocp(...)["y"]`) so the file is correct before Solver is run; a note says "Yellow cells are Solver decision variables; re-run Solver to confirm." Everything else is a formula:

```python
ws.write_formula("B10", "=SUMPRODUCT(B9:K9,$B$4:$K$4)")
ws.write_formula("B11", "=SUMPRODUCT(MMULT(B9:K9,S7_Cov!$B$2:$K$11),B9:K9)")
ws.write_formula("B12", "=SQRT(B11)")
ws.write_formula("B16", "=SUMPRODUCT(B15:K15,$B$4:$K$4)")
ws.write_formula("B17", "=SUMPRODUCT(MMULT(B15:K15,S7_Cov!$B$2:$K$11),B15:K15)")
ws.write_formula("B18", "=SQRT(B17)")
ws.write_formula("B19", "=(B16-$B$6)/B18")
ws.write_formula("B20", '=COUNTIF(B15:K15,">0.0001")')
ws.write_formula("B24", "=$B$23*B15")           # fill across K24
ws.write_formula("B25", "=1-B23")
ws.write_formula("B26", "=$B$6+B23*(B16-$B$6)")
ws.write_formula("B27", "=B23*B18")
ws.write_formula("B28", "=B26-0.5*B29*B27^2")
ws.write_number("B29", A)
ws.write_formula("B30", "=(B16-$B$6)/(B29*B17)")
ws.write_formula("L9", "=SUM(B9:K9)"); ws.write_formula("L15", "=SUM(B15:K15)")
# B4:K4 =S6_Returns!B64.. ; B5:K5 =S6_Returns!B65.. ; B6 =S6_Returns!B66 ; B3:K3 tickers
```

Step-by-step Solver instructions as text in rows 33-50 (MVP: min `B11`, change `B9:K9`, constraints `B9:K9>=0`, `L9=1`, GRG Nonlinear; ORP: max `B19`, change `B15:K15`, `>=0`, `L15=1`, `B20>=2`; OCP: max `B28`, change `B23`, `B23>=0`). Best-effort pre-load of the ORP model:

```python
for name, val in {"solver_opt": "=S8_Solver!$B$19", "solver_typ": "=1", "solver_val": "=0",
                  "solver_adj": "=S8_Solver!$B$15:$K$15", "solver_num": "=2", "solver_eng": "=1",
                  "solver_neg": "=1", "solver_lhs1": "=S8_Solver!$L$15", "solver_rel1": "=2", "solver_rhs1": "=1",
                  "solver_lhs2": "=S8_Solver!$B$20", "solver_rel2": "=3", "solver_rhs2": "=2"}.items():
    wb.define_name(f"S8_Solver!{name}", val)
```

- [ ] **Step 3: Implement `write_mvf_chart` (S2)**

Table: Index, w1..w10 (80 frontier weight rows from `frontier()`), Return `=SUMPRODUCT(B2:K2,S8_Solver!$B$4:$K$4)`, SD `=SQRT(SUMPRODUCT(MMULT(B2:K2,S7_Cov!$B$2:$K$11),B2:K2))`. Marker table: MVP/ORP/OCP linked to `S8_Solver` (`B10/B12`, `B16/B18`, `B26/B27`), CAL points `(0, rf)` and `(1.6*sd_ORP, rf + 1.6*(ret_ORP - rf))`, and the 10 ETFs from `S6_Returns` stats. Chart: `wb.add_chart({"type": "scatter", "subtype": "smooth"})` with series: frontier (line), CAL (dashed line), MVP, ORP, OCP (large markers, `data_labels: {"series_name": True, "position": "right"}`), ETFs (small grey markers, `data_labels: {"custom": [{"value": t} for t in ALL]}`). Axes "Annualised st. dev." and "Annualised return" in percent, title "Minimum Variance Frontier, CAL, MVP / ORP / OCP (A=7)". Insert at `N2`, size 900x560.

- [ ] **Step 4: Implement `write_summary` (S1)**

Rows = ETFs (10) + "Risk-free"; columns = MVP, ORP, OCP (4c), OCP (6b). MVP/ORP/OCP(4c) weights link to `S8_Solver` (`B9:K9`, `B15:K15`, `B24:K24`, rf `B25`). OCP (6b) weights are yellow inputs from `forward_model.forward_ocp()` labelled "from Step 6 model". Below: Return, SD and Sharpe as formulas (`SUMPRODUCT` against `S8_Solver!$B$4:$K$4`, and SD via a helper block that lays each weight vector as a row so `MMULT` works without array entry). Row 12 holds "Return". Add a Step 8 block: start $100,000, end values and metrics from `evaluate.py` written as numbers, labelled "computed in Python (evaluate.py)".

- [ ] **Step 5: Implement `write_cover`**

Fields: Section number, Group number (`B#_Group#`), member names and matric numbers (blank yellow cells for the user), colour legend (yellow = input / Solver decision, blue header = labels, white = formula), sheet index with one-line descriptions, data sources and conventions, the 48-observation caveat.

- [ ] **Step 6: Run tests and open the file in Excel**

Run: `.venv/bin/pytest tests/test_workbook_structure.py -v && .venv/bin/python build_workbook.py && open -a "Microsoft Excel" FIN3702B_Portfolio.xlsx`
Expected: tests PASS; workbook opens with no `#NAME?`/`#VALUE!`, chart shows frontier, CAL and labelled points.

- [ ] **Step 7: Commit**

```bash
git add build_workbook.py tests/test_workbook_structure.py
git commit -m "feat: Solver sheet, native MVF chart, summary and cover"
```

---

### Task 8: Recalculation check, Solver run and Python-Excel reconciliation

**Files:**
- Create: `tests/reconcile.py` (script, run manually), `docs/reconciliation.md`

**Interfaces:**
- Consumes: the saved workbook (after the user runs Solver), `optimize.*`
- Produces: `reconcile.compare(xlsx_path) -> DataFrame` with columns `quantity, python, excel, abs_diff, ok`

- [ ] **Step 1: Write `tests/reconcile.py`**

```python
import sys
import numpy as np
import openpyxl
import pandas as pd
from optimize import estimation_inputs, mvp, orp, ocp, port_stats

TOL = 0.005


def compare(path):
    ws = openpyxl.load_workbook(path, data_only=True)["S8_Solver"]
    r, rf_m, st, S, rf = estimation_inputs()
    mu, Sv = st["ret"].values, S.values
    wm, wo = mvp(Sv), orp(mu, Sv, rf)
    o = ocp(wo, mu, Sv, rf, 7)
    rows = []
    for name, py, cell in [
        ("MVP return", port_stats(wm, mu, Sv)[0], "B10"), ("MVP sd", port_stats(wm, mu, Sv)[1], "B12"),
        ("ORP return", port_stats(wo, mu, Sv)[0], "B16"), ("ORP sd", port_stats(wo, mu, Sv)[1], "B18"),
        ("ORP Sharpe", (port_stats(wo, mu, Sv)[0] - rf) / port_stats(wo, mu, Sv)[1], "B19"),
        ("OCP y", o["y"], "B23"), ("OCP return", o["ret"], "B26"), ("OCP sd", o["sd"], "B27")]:
        x = ws[cell].value
        rows.append((name, py, x, abs(py - x), abs(py - x) <= TOL))
    for j, t in enumerate(r.columns):
        for lab, rown, wv in (("MVP", 9, wm[j]), ("ORP", 15, wo[j])):
            x = ws.cell(row=rown, column=2 + j).value
            rows.append((f"{lab} w[{t}]", wv, x, abs(wv - x), abs(wv - x) <= TOL))
    return pd.DataFrame(rows, columns=["quantity", "python", "excel", "abs_diff", "ok"])


if __name__ == "__main__":
    df = compare(sys.argv[1])
    print(df.round(6).to_string()); print("ALL OK" if df.ok.all() else "MISMATCH")
```

- [ ] **Step 2: Verify formulas compute in real Excel (not just in xlsxwriter)**

```bash
osascript -e 'tell application "Microsoft Excel"
  open POSIX file "'"$PWD"'/FIN3702B_Portfolio.xlsx"
  save active workbook in POSIX file "'"$PWD"'/data/recalc.xlsx" as workbook normal file format
  close active workbook saving no
end tell'
.venv/bin/python -c "
import openpyxl
wb=openpyxl.load_workbook('data/recalc.xlsx',data_only=True)
bad=[(s.title,c.coordinate,c.value) for s in wb for row in s.iter_rows() for c in row if isinstance(c.value,str) and c.value.startswith('#')]
print('errors:',bad[:10]); print('B64',wb['S6_Returns']['B64'].value)"
```
Expected: `errors: []` and a numeric `B64`. If AppleScript is blocked, ask the user to open the workbook, press Save, and send back the file.

- [ ] **Step 3: User runs Solver (manual checkpoint, about 5 minutes)**

Ask the user: open `FIN3702B_Portfolio.xlsx` → `S8_Solver`. If the pre-loaded ORP model is not present, follow the instructions in rows 33-50 for MVP, ORP, OCP (GRG Nonlinear, "Make unconstrained variables non-negative" ticked). To make the check meaningful, first overwrite the yellow weight cells with equal weights (0.1 each, OCP y = 0.5), then run Solver, then Save. Record whether the Solver pre-load worked.

- [ ] **Step 4: Reconcile**

Run: `.venv/bin/python tests/reconcile.py FIN3702B_Portfolio.xlsx`
Expected: `ALL OK`. If a weight mismatches while return/sd match, Solver found a nearby optimum (flat objective); compare objective values. If returns/sd mismatch, check which convention differs (adjusted vs unadjusted, `STDEV.S`, Rf annualisation) and fix whichever side is wrong.

- [ ] **Step 5: Write `docs/reconciliation.md` and commit**

Paste the comparison table and a one-paragraph explanation of any difference.
`git add tests/reconcile.py docs/reconciliation.md && git commit -m "test: Excel Solver vs Python reconciliation"`

---

### Task 9: LLM Prompts A and B (optimisation code, frontier chart) with discrepancy loop

**Files:**
- Create: `docs/deliverables/prompts_log.md` (working log), `llm_code/optimiser_v1.py` (the LLM's code, saved verbatim), `tests/check_llm_results.py`

**Interfaces:**
- Consumes: Python truth values from `optimize.py`
- Produces: `llm_code/results.json` with keys `mvp`, `orp`, `ocp` each `{weights: {ticker: float}, ret: float, sd: float}`; `llm_code/ai_results.xlsx` (results worksheet); `llm_code/mvf_ai.png`

- [ ] **Step 1: Write the acceptance check `tests/check_llm_results.py`**

```python
import json, sys
from optimize import estimation_inputs, mvp, orp, ocp, port_stats

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
```

- [ ] **Step 2: Prompt A, version 1 (paste into a fresh chat with no files attached; record exact text and date)**

```text
You are a quantitative finance programmer. Write ONE self-contained Python 3 script
(runs top-to-bottom in Google Colab with only pip installs at the top) that does the following.

DATA
1. Download MONTHLY ADJUSTED CLOSE prices from Yahoo Finance (yfinance) for these 10 ETFs:
   SPY, IWM, VEA, VWO, XLE, QQQ, AGG, TIP, HYG, GLD.
   Download daily data from 2020-11-20 to 2026-01-10 with auto_adjust=False, take the "Adj Close"
   column, and resample to month-end using the LAST available trading day of each month.
   Keep month-ends from 2020-12-31 to 2024-12-31.
2. Download the Fama-French monthly factors from
   https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip
   Use the monthly table only (rows whose first field is a 6-digit YYYYMM). Take the RF column,
   which is in PERCENT, divide by 100, and index by month-end.
3. Compute simple monthly returns = P_t / P_(t-1) - 1. The first return is Jan 2021, the last is
   Dec 2024, giving exactly 48 observations per ETF. Assert that.

STATISTICS (per ETF and for portfolios)
- Annualised return = arithmetic mean of monthly returns x 12.
- Annualised standard deviation = sample standard deviation (ddof=1) of monthly returns x sqrt(12).
- Annualised risk-free rate = mean of the 48 monthly RF values x 12.
- Sharpe ratio = (annualised return - annualised risk-free) / annualised standard deviation.
- Annualised covariance matrix = sample covariance (ddof=1) of monthly returns x 12.

OPTIMISATION (scipy.optimize.minimize, method SLSQP, bounds 0..1 for every weight, weights sum to 1,
NO short selling; try at least 10 different starting points and keep the best solution)
a) MVP: minimise portfolio variance.
b) ORP: maximise the Sharpe ratio. The ORP must hold at least 2 ETFs with weight > 0.0001;
   if it does not, raise an error that says to choose other ETFs.
c) OCP with risk aversion A = 7: y = (E[r_ORP] - rf) / (A x variance_ORP).
   OCP risky weights = y x ORP weights; the remainder (1 - y) is in the risk-free asset
   (negative if y > 1, meaning borrowing at the risk-free rate).
   OCP return = rf + y x (E[r_ORP] - rf); OCP sd = y x sd_ORP.

OUTPUT
- Print a table of the 10 ETFs with annualised return, sd, Sharpe.
- Print weights, annualised return, sd and Sharpe for MVP, ORP and OCP.
- Write results to an Excel file "ai_results.xlsx" (openpyxl or xlsxwriter) with one worksheet
  "Results" showing those tables, and ALSO save results.json with this exact structure:
  {"mvp": {"weights": {...}, "ret": x, "sd": x}, "orp": {...}, "ocp": {...}} where ret and sd
  are annualised decimals (0.10 = 10%).
Return only the code in one block.
```

Run the returned code locally (or in Colab), save it as `llm_code/optimiser_v1.py`, then run `.venv/bin/python tests/check_llm_results.py llm_code/results.json`.

- [ ] **Step 3: Discrepancy loop (repeat until the check prints PASS)**

For each FAIL, record in `docs/deliverables/prompts_log.md`: the prompt version, the numbers, the root cause, and the exact wording added to fix it. Likely root causes to test first: (1) `Close` instead of `Adj Close`, (2) `ddof=0`, (3) risk-free not divided by 100 or annualised by compounding, (4) month-end alignment (`resample("M")` vs the French index), (5) a single SLSQP start landing on a local optimum, (6) Dec 2020 counted as a return (49 observations), (7) the fetched window includes 2025. Fix the prompt, not the code, then re-run in a fresh chat. Save every version.

- [ ] **Step 4: Prompt B (frontier chart written into Excel), then refine with the same loop**

Content requirements (write it out in full in the log, same style as Prompt A, self-contained, repeating the full statistics spec so it does not depend on Prompt A): compute the long-only minimum variance frontier with 80 target-return points from min(mu) to max(mu); plot it with the CAL from (0, rf) through the ORP and beyond; label MVP, ORP, OCP and the 10 ETFs; write the chart onto an Excel worksheet named "MVF" in `ai_results.xlsx` (native chart via xlsxwriter or an inserted matplotlib PNG), and also save `mvf_ai.png`. Acceptance: the PNG and the sheet exist, the three labelled points match `results.json` within tolerance, CAL passes through ORP and OCP.

- [ ] **Step 5: Variability test (beyond-excellent)**

Run the final Prompt A in 3 fresh chats; run each output through `check_llm_results.py`; log pass/fail and what differed. This is evidence for the Step 9 reliability discussion.

- [ ] **Step 6: Commit**

`git add docs/deliverables/prompts_log.md llm_code tests/check_llm_results.py && git commit -m "docs: LLM optimisation prompts with discrepancy log"`

---

### Task 10: LLM Prompts C, D, E (macro download, forward model, justification)

**Files:**
- Modify: `docs/deliverables/prompts_log.md`
- Create: `llm_code/macro_download.py`, `llm_code/forward_model_llm.py`, `llm_code/forward_results.json`

**Interfaces:**
- Consumes: `forward_model.forward_ocp()` as the internal reference (not given to the LLM)
- Produces: `llm_code/forward_results.json` with `{"weights": {...}, "ret": x, "sd": x, "sharpe": x}` for the LLM's 6b OCP

- [ ] **Step 1: Prompt C (download macro data 2021-2024)**

Requirements for the text: free FRED CSV endpoint `https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES>` (no API key); series DGS10, T10Y2Y, VIXCLS, FEDFUNDS, CPIAUCSL, UNRATE (one line each on why it matters for these asset classes); monthly aggregation (daily series: monthly mean); treat `.` as missing; **hard rule: no observation after 2024-12-31 may be downloaded or used**; save to `macro.csv`; print the last date per series; include an assertion for the cap.

- [ ] **Step 2: Prompt D (forward-looking model, A = 7)**

Requirements for the text: re-state the Prompt A data and statistics spec; features lagged by one month (CPI and unemployment one extra month for publication delay); an explicitly regularised model (ridge, alpha by leave-one-out CV) from the macro features to each ETF's monthly returns over Jan 2021 to Dec 2024; forecast 2025 expected returns using the Dec 2024 macro state only; covariance from Ledoit-Wolf on the same 48 months; then the same ORP (>= 2 ETFs, long-only) and OCP (A = 7) as in Prompt A on the forecast inputs; output weights, return, sd, Sharpe to `forward_results.json` and an Excel worksheet; print model diagnostics (chosen alphas, LOO R-squared). **Hard rule: do not use any data dated after 2024-12-31.**
Acceptance: runs end to end; no data after the cap (assert in code); weights sum to 1; at least 2 ETFs in ORP; diagnostics printed. It will not match `forward_ocp()` exactly because the LLM may choose different features or regularisation; log the differences and judge which is defensible (document, do not force a match).

- [ ] **Step 3: Prompt E (justification)**

Text: provide the weights, the forecast returns and the chosen model's coefficients as pasted data, and ask for a justification covering macro drivers by asset class, why each ETF got its weight, what risks could make it wrong, and an honest statement of statistical uncertainty given 48 observations. Check that the answer cites coefficients that actually appear in the output (reject hallucinated numbers).

- [ ] **Step 4: Fresh-chat reproduction check**

For each of Prompts A to E in final form, paste into a brand-new chat with no prior context; confirm the output runs and passes its check. Record the date and model name in the log.

- [ ] **Step 5: Commit**

`git add docs/deliverables/prompts_log.md llm_code && git commit -m "docs: macro, forward-model and justification prompts"`

---

### Task 11: Word/PDF document (prompts, Step 8, Step 9)

**Files:**
- Create: `make_report.py`, `docs/deliverables/report_source.md`, `Prompts_and_Answers.docx`, `docs/results_step8.txt`

**Interfaces:**
- Consumes: `prompts_log.md`, `evaluate.*`, `forward_model.forward_ocp`, `robustness.*`, `docs/results_*.txt`

- [ ] **Step 1: Compute the Step 8 results**

```bash
.venv/bin/python -c "
from optimize import *; from evaluate import *; from forward_model import forward_ocp
r,rf_m,st,S,rf=estimation_inputs(); mu=st['ret'].values
a=ocp(orp(mu,S.values,rf),mu,S.values,rf,7); b=forward_ocp()['ocp']
r25,rf25=holdout_inputs()
for lab,o in (('4c',a),('6b',b)):
    for reb in (False,True):
        w=wealth(o['w_risky'],o['w_rf'],r25,rf25,rebalance=reb)
        print(lab,'rebal' if reb else 'B&H',{k:round(v,4) for k,v in metrics(w,rf25,r25['SPY']).items()})
print('SPY buy&hold end', 100000*(1+r25['SPY']).prod())
" | tee docs/results_step8.txt
```

- [ ] **Step 2: Write `report_source.md` with these sections**

1. How to reproduce (environment, one-paragraph overview). 2. Prompts A to E: each as v1, discrepancy log, final version in code blocks, screenshot placeholders named `fig_promptA_v1.png` etc. 3. Step 8 answer: dollar end values for both OCPs, a metrics table (end value, total return, Sharpe, Sortino, Treynor, Jensen alpha, M2, max drawdown, information ratio), a verdict that explains which metric supports which conclusion, and the caveat that 12 observations make these metrics statistically weak (buy-and-hold is the primary reading; rebalanced shown as sensitivity). 4. Step 9 evaluation in five headed parts (strengths, weaknesses, risks, ethical considerations, practical limitations), each with at least three concrete points tied to our own findings and a mitigation for every risk: weaknesses = code differing between runs (variability test), silent convention errors (discrepancy log), hallucinated justifications; risks = data leakage, overfitting 48 observations (Ledoit-Wolf and perturbation numbers from `docs/results_robustness.txt`), model risk; ethics = suitability and fiduciary duty, transparency/explainability, accountability, data provenance, bias toward past regimes, client-data privacy, disclosure that an LLM was used; practical = need for human review, reproducibility, API/data costs, regulatory (MAS) expectations, monitoring. 5. The 48-observation caveat with the quantified fragility numbers.

- [ ] **Step 3: Build the docx**

Use the `anthropic-skills:docx` skill (or `python-docx`) to render `report_source.md` into `Prompts_and_Answers.docx` with headings, monospace code blocks, and tables. Open it and check that headings, tables and code blocks render.

- [ ] **Step 4: Commit**

`git add make_report.py docs/deliverables/report_source.md Prompts_and_Answers.docx docs/results_step8.txt && git commit -m "docs: prompts document with Step 8 and Step 9 answers"`

---

### Task 12: Demo support, final QA against the rubric, packaging

**Files:**
- Create: `docs/deliverables/demo_runbook.md`, `docs/deliverables/qa_cheatsheet.md`, `package.py`

- [ ] **Step 1: Demo runbook (for the group's live demo)**

One page: which single prompt to paste, expected runtime, expected output numbers (from Task 9), a fallback pre-run notebook/screenshots if Colab or Yahoo fails, and the 3 failure modes seen in testing with the exact fix.

- [ ] **Step 2: Q&A cheat sheet for the sceptical client**

Answers (with our numbers) to: why 48 months, how stable are the weights (perturbation/bootstrap results), why not just buy SPY, what if the LLM hallucinates, who is accountable, how do you know the code is right (Excel vs Python vs LLM reconciliation), what happens in a regime change, cost, and data privacy.

- [ ] **Step 3: Final rubric audit**

Open the workbook and tick each row of the Rubric Coverage Map: all 9 sheets present; Sheets 6, 7, 8 formulas only (`tests/test_workbook_structure.py`); no `#` errors (Task 8 Step 2); charts labelled; reconciliation `ALL OK`; LLM check `PASS` three times; prompts reproducible in fresh chats; Step 8, Step 9 and caveat sections present; cover sheet filled in by the user (section, group, names, matric numbers).

- [ ] **Step 4: Package**

`package.py` copies the deliverables into `B#_Group#/` and zips them, with the group token as an argument:

```python
import shutil, sys
from pathlib import Path

name = sys.argv[1]                       # e.g. B3_Group7
out = Path(name); out.mkdir(exist_ok=True)
for f in ["FIN3702B_Portfolio.xlsx", "Prompts_and_Answers.docx", "llm_code/ai_results.xlsx"]:
    shutil.copy(f, out / Path(f).name)
shutil.make_archive(name, "zip", out)
print(f"wrote {name}.zip")
```

Run: `.venv/bin/python package.py B#_Group#` with the real values, then copy the zip and the deliverables into the Desktop project folder. The user uploads the zip to Canvas before Fri 30 Oct 2026, 5pm (two submissions allowed).

- [ ] **Step 5: Commit**

`git add docs/deliverables package.py && git commit -m "docs: demo runbook, Q&A sheet, packaging"`

---

## Self-Review Notes

- **Spec coverage:** data (Task 1), Steps 3-4 (2, 6-8), Step 5 (9), Step 6 (4, 10), Step 7 (data layer holds 2025), Step 8 (3, 11), Step 9 (11), Ledoit-Wolf and fragility (5, 11), workbook sheets 1-8 plus cover (6-7), caveat (11), packaging (12).
- **Open decisions flagged to the user:** (a) no-short applies to the MVP and frontier as well as the ORP; (b) Step 8 primary reading is buy-and-hold; (c) the Solver pre-load is best-effort.
- **Type consistency:** `ocp()` returns `w_risky`, `w_rf`, `ret`, `sd`, `y`, `utility`, used identically in Tasks 3, 4, 5, 7, 8, 11. `estimation_inputs()` returns the same 5-tuple everywhere.
