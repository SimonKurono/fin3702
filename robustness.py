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
