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
