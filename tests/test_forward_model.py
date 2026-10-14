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


def test_ridge_floor_prevents_overfit_and_absurd_forecasts():
    # With n=48 an unregularised fit on the 2022 bond crash gave AGG +18.9%/yr and a 3.6x levered OCP.
    from forward_model import ALPHA_FLOOR
    r, rf_m, st, S, rf = estimation_inputs()
    out = fit_forward(r, build_features(load_macro()))
    assert (out["alpha"] >= ALPHA_FLOOR - 1e-9).all()
    assert (out["mu_fwd"] - st["ret"]).abs().max() < 0.15      # forecasts stay near history
    assert forward_ocp()["ocp"]["y"] < 2.5                     # no absurd leverage
