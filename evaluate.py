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
