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
