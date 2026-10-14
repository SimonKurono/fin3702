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
