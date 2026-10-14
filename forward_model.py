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
ALPHA_FLOOR = 50.0   # ~ sample size (n=48): stops a loose fit to one regime (2022 bond crash)


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
    rcv = RidgeCV(alphas=np.logspace(np.log10(ALPHA_FLOOR), 3, 30), alpha_per_target=True).fit(Xs, r_est.values)
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
