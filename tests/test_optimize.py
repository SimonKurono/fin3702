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
    mu = np.array([0.30, -0.05]); S = np.array([[0.01, 0.0], [0.0, 0.04]])
    with pytest.raises(ORPConcentrationError):
        orp(mu, S, rf=0.0)  # asset 2 has negative excess return -> ORP = 100% asset 1


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
