import pandas as pd
from config import ALL, MACRO_CAP
from data import load_prices, load_french, rf_decimal, load_macro


def test_prices_window_and_no_gaps():
    adj, close = load_prices()
    assert list(adj.columns) == ALL and list(close.columns) == ALL
    assert adj.index[0] == pd.Timestamp("2020-12-31")
    assert adj.index[-1] == pd.Timestamp("2025-12-31")   # no partial 2026 month
    assert len(adj) == 61 and not adj.isna().any().any()


def test_rf_is_decimal_monthly():
    rf = rf_decimal(load_french())
    window = rf["2021-01-31":"2025-12-31"]
    assert len(window) == 60
    assert window.between(0, 0.01).all()      # percent/decimal mix-up would exceed this


def test_macro_has_no_data_after_cap():
    m = load_macro()
    assert m.index.max() <= pd.Timestamp(MACRO_CAP)
    assert m.index.min() <= pd.Timestamp("2019-01-31")
    assert not m["2020-01-31":].isna().any().any()
