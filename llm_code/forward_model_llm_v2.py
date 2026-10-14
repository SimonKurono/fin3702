# =============================================================================
# Forward-looking macro-driven portfolio selection for 2025
# Uses ONLY information dated <= 2024-12-31 (asserted throughout).
# =============================================================================
import sys, subprocess
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q",
                       "yfinance", "scikit-learn", "scipy", "openpyxl",
                       "pandas", "numpy", "requests"])

import io, json, re, zipfile, warnings
import numpy as np
import pandas as pd
import requests
import yfinance as yf
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf
from sklearn.linear_model import RidgeCV
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 50)

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
CUTOFF = pd.Timestamp("2024-12-31")            # HARD RULE: nothing after this date
TICKERS = ["SPY", "IWM", "VEA", "VWO", "XLE", "QQQ", "AGG", "TIP", "HYG", "GLD"]
A_RISK_AVERSION = 7.0
ALPHAS = np.logspace(np.log10(50), 3, 30)      # never lighter than 50
HEADERS = {"User-Agent": "Mozilla/5.0 (research script)"}


def assert_cutoff(obj, name):
    """Assert that no observation is dated after the cutoff."""
    idx = obj.index if hasattr(obj, "index") else pd.DatetimeIndex(obj)
    assert len(idx) > 0, f"{name}: empty"
    assert pd.Timestamp(idx.max()) <= CUTOFF, f"{name}: data after {CUTOFF.date()} found ({idx.max()})"


def to_month_end(s, how):
    """Aggregate a datetime-indexed Series to calendar month-end labels."""
    s = s.dropna()
    g = s.groupby(s.index.to_period("M"))
    out = g.last() if how == "last" else g.mean()
    out.index = out.index.to_timestamp(how="end").normalize()
    return out


# -----------------------------------------------------------------------------
# 1. ETF DATA (monthly adjusted close)
# -----------------------------------------------------------------------------
raw = yf.download(TICKERS, start="2020-11-20", end="2025-01-01",
                  auto_adjust=False, progress=False)
if isinstance(raw.columns, pd.MultiIndex):
    px_daily = raw["Adj Close"].copy()
else:
    px_daily = raw[["Adj Close"]].copy()
px_daily = px_daily[TICKERS]
px_daily.index = pd.to_datetime(px_daily.index).tz_localize(None)
assert_cutoff(px_daily, "daily ETF prices")

# last trading day of each month, labelled by calendar month-end
g = px_daily.groupby(px_daily.index.to_period("M"))
px_m = g.last()
px_m.index = px_m.index.to_timestamp(how="end").normalize()
px_m = px_m.loc["2020-12-31":"2024-12-31"]
assert px_m.shape[0] == 49, f"Expected 49 month-end prices, got {px_m.shape[0]}"
assert not px_m.isna().any().any(), "Missing ETF prices"
assert_cutoff(px_m, "monthly ETF prices")

rets = px_m / px_m.shift(1) - 1
rets = rets.dropna()
assert rets.shape[0] == 48, f"Expected 48 monthly returns, got {rets.shape[0]}"
assert rets.index.min() == pd.Timestamp("2021-01-31") and rets.index.max() == pd.Timestamp("2024-12-31")
assert_cutoff(rets, "monthly returns")

# -----------------------------------------------------------------------------
# 2. RISK-FREE RATE (Fama-French)
# -----------------------------------------------------------------------------
FF_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip"
resp = requests.get(FF_URL, headers=HEADERS, timeout=60)
resp.raise_for_status()
with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
    name = [n for n in zf.namelist() if n.lower().endswith(".csv")][0]
    text = zf.read(name).decode("latin-1")

rf_rows = {}
for line in text.splitlines():
    parts = [p.strip() for p in line.split(",")]
    if len(parts) >= 5 and re.fullmatch(r"\d{6}", parts[0]):   # monthly table only
        ym = parts[0]
        dt = pd.Timestamp(int(ym[:4]), int(ym[4:]), 1) + pd.offsets.MonthEnd(0)
        if dt > CUTOFF:           # discard immediately, never used
            continue
        rf_rows[dt] = float(parts[4]) / 100.0                  # RF column, percent -> decimal
rf_m = pd.Series(rf_rows).sort_index()
rf_m = rf_m.loc["2021-01-31":"2024-12-31"]
assert len(rf_m) == 48, f"Expected 48 RF observations, got {len(rf_m)}"
assert rf_m.index.equals(rets.index), "RF index does not align with returns"
assert_cutoff(rf_m, "Fama-French RF")
rf = float(rf_m.mean() * 12)

# -----------------------------------------------------------------------------
# 3. MACRO DATA (FRED)
# -----------------------------------------------------------------------------
def fred(series_id):
    # cosd/coed restrict the download itself to 2019-01-01..2024-12-31
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    r = requests.get(url, params={"cosd": "2019-01-01", "coed": "2024-12-31"},
                     headers=HEADERS, timeout=60)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    dcol, vcol = df.columns[0], df.columns[1]
    s = pd.Series(pd.to_numeric(df[vcol].replace(".", np.nan), errors="coerce").values,
                  index=pd.to_datetime(df[dcol]), name=series_id)
    s = s.loc["2019-01-01":"2024-12-31"]            # defensive filter
    assert_cutoff(s, f"FRED {series_id}")
    return s

dgs10 = fred("DGS10")
t10y2y = fred("T10Y2Y")
vix = fred("VIXCLS")
ffr = fred("FEDFUNDS")
cpi = fred("CPIAUCSL")
unr = fred("UNRATE")

full_idx = pd.period_range("2019-01", "2024-12", freq="M").to_timestamp(how="end").normalize()

feat = pd.DataFrame(index=full_idx)
feat["y10"] = to_month_end(dgs10, "last")          # last available daily value of the month
feat["curve"] = to_month_end(t10y2y, "last")
feat["vix"] = to_month_end(vix, "mean")            # monthly mean of daily VIX
feat["ffr"] = to_month_end(ffr, "last")            # monthly series -> month-end
cpi_m = to_month_end(cpi, "last").reindex(full_idx)
unr_m = to_month_end(unr, "last").reindex(full_idx)
feat["cpi_yoy"] = 100.0 * (cpi_m / cpi_m.shift(12) - 1.0)
feat["unrate"] = unr_m

# Publication delay: month-t feature uses the value of month t-1
feat["cpi_yoy"] = feat["cpi_yoy"].shift(1)
feat["unrate"] = feat["unrate"].shift(1)
FEATS = ["y10", "curve", "vix", "ffr", "cpi_yoy", "unrate"]
feat = feat[FEATS]
assert_cutoff(feat, "macro features")
assert not feat.loc["2020-12-31":"2024-12-31"].isna().any().any(), "Missing macro features"

# -----------------------------------------------------------------------------
# 4. FORECASTING MODEL (ridge, LOO-CV over alphas >= 50)
# -----------------------------------------------------------------------------
X_lag = feat.shift(1)                               # features known at end of month t-1
X_train = X_lag.loc[rets.index]
assert not X_train.isna().any().any(), "Missing lagged features in training window"
assert X_train.shape == (48, 6)
x_new = feat.loc[pd.Timestamp("2024-12-31")]        # Dec 2024 features -> forecast month
assert x_new.notna().all()

scaler = StandardScaler().fit(X_train.values)
Z = scaler.transform(X_train.values)
Y = rets[TICKERS].values

ridge = RidgeCV(alphas=ALPHAS, alpha_per_target=True)   # efficient leave-one-out CV
ridge.fit(Z, Y)
alpha_sel = np.atleast_1d(ridge.alpha_)
assert (alpha_sel >= 50 - 1e-9).all()

def loo_r2(Zs, y, alpha):
    """Exact leave-one-out R^2 for ridge with unpenalised intercept."""
    n, p = Zs.shape
    Zc = Zs - Zs.mean(axis=0)
    H = Zc @ np.linalg.solve(Zc.T @ Zc + alpha * np.eye(p), Zc.T) + 1.0 / n
    e = y - H @ y
    loo = e / (1.0 - np.diag(H))
    return 1.0 - np.sum(loo ** 2) / np.sum((y - y.mean()) ** 2)

z_new = scaler.transform(x_new.values.reshape(1, -1))
pred_monthly = ridge.predict(z_new).ravel()
mu_fwd = pd.Series(pred_monthly * 12.0, index=TICKERS)
hist_mu = rets[TICKERS].mean() * 12.0

diag = pd.DataFrame({
    "alpha": alpha_sel,
    "LOO_R2": [loo_r2(Z, Y[:, i], alpha_sel[i]) for i in range(len(TICKERS))],
    "mu_fwd": mu_fwd.values,
    "hist_mu": hist_mu.values,
}, index=TICKERS)
coefs = pd.DataFrame(ridge.coef_, index=TICKERS, columns=FEATS)

print("=" * 80)
print(f"Annualised risk-free rate (mean RF Jan21-Dec24 x 12): {rf:.4%}")
print("\nDec-2024 feature values used for the forecast:")
print(x_new.round(4).to_string())
print("\nRidge diagnostics (alpha, leave-one-out R2, forecast vs historical mean):")
print(diag.round(4).to_string())
print("\nRidge coefficients (standardised features):")
print(coefs.round(5).to_string())

# SANITY CHECK 1: forecasts must be near each ETF's own historical mean
gap = (mu_fwd - hist_mu).abs()
if (gap > 0.15).any():
    bad = gap[gap > 0.15]
    raise AssertionError("mu_fwd deviates >0.15 from historical annualised mean for: "
                         + ", ".join(f"{k} (gap {v:.3f})" for k, v in bad.items()))

# -----------------------------------------------------------------------------
# 5. COVARIANCE (Ledoit-Wolf, annualised)
# -----------------------------------------------------------------------------
lw = LedoitWolf().fit(rets[TICKERS].values)
Sigma = lw.covariance_ * 12.0
mu = mu_fwd.values

# -----------------------------------------------------------------------------
# 6. PORTFOLIOS
# -----------------------------------------------------------------------------
n = len(TICKERS)

def neg_sharpe(w):
    var = w @ Sigma @ w
    return -((w @ mu - rf) / np.sqrt(max(var, 1e-14)))

cons = ({"type": "eq", "fun": lambda w: np.sum(w) - 1.0},)
bnds = [(0.0, 1.0)] * n
rng = np.random.default_rng(42)
starts = [np.ones(n) / n] + [np.eye(n)[i] * 0.9 + 0.1 / n for i in range(n)]
starts += [rng.dirichlet(np.ones(n)) for _ in range(20)]
assert len(starts) >= 10

best = None
for w0 in starts:
    res = minimize(neg_sharpe, w0, method="SLSQP", bounds=bnds, constraints=cons,
                   options={"maxiter": 1000, "ftol": 1e-12})
    if res.success and abs(res.x.sum() - 1) < 1e-6 and (res.x > -1e-8).all():
        if best is None or res.fun < best.fun:
            best = res
if best is None:
    raise RuntimeError("ORP optimisation failed from all starting points")

w_orp = np.clip(best.x, 0, 1)
w_orp = w_orp / w_orp.sum()
if (w_orp > 1e-4).sum() < 2:
    raise ValueError("ORP holds fewer than 2 ETFs with weight > 0.0001: choose other ETFs.")

ret_orp = float(w_orp @ mu)
var_orp = float(w_orp @ Sigma @ w_orp)
sd_orp = float(np.sqrt(var_orp))

# OCP
y_risky = (ret_orp - rf) / (A_RISK_AVERSION * var_orp)
# SANITY CHECK 2
if not y_risky < 2.5:
    raise AssertionError(f"OCP risky share y = {y_risky:.3f} is not below 2.5")

w_ocp = y_risky * w_orp
w_rf = 1.0 - y_risky
ocp_ret = rf + y_risky * (ret_orp - rf)
ocp_sd = y_risky * sd_orp
ocp_sharpe = (ocp_ret - rf) / ocp_sd

# -----------------------------------------------------------------------------
# 7. OUTPUT
# -----------------------------------------------------------------------------
print("\n" + "=" * 80)
print("Forward-looking annualised expected returns mu_fwd (2025):")
print(mu_fwd.round(4).to_string())
print("\nORP: E[r] = {:.4%}, sd = {:.4%}, Sharpe = {:.4f}".format(
    ret_orp, sd_orp, (ret_orp - rf) / sd_orp))
w_table = pd.DataFrame({"ORP": w_orp, "OCP": w_ocp}, index=TICKERS)
w_table.loc["RiskFree"] = [0.0, w_rf]
print("\nWeights:")
print(w_table.round(4).to_string())
print(f"\nOCP (A = {A_RISK_AVERSION:g}): y = {y_risky:.4f}")
print(f"  Expected return: {ocp_ret:.4%}")
print(f"  Standard deviation: {ocp_sd:.4%}")
print(f"  Sharpe ratio: {ocp_sharpe:.4f}")

weights_out = {t: float(w) for t, w in zip(TICKERS, w_ocp)}
weights_out["RiskFree"] = float(w_rf)
results = {
    "weights": weights_out,
    "ret": float(ocp_ret),
    "sd": float(ocp_sd),
    "sharpe": float(ocp_sharpe),
    "y": float(y_risky),
    "mu_fwd": {t: float(v) for t, v in mu_fwd.items()},
}
with open("forward_results.json", "w") as f:
    json.dump(results, f, indent=2)

summary = pd.DataFrame({
    "Metric": ["Risk-free rate (annual)", "OCP expected return", "OCP standard deviation",
               "OCP Sharpe ratio", "Risky share y", "Risk aversion A",
               "ORP expected return", "ORP standard deviation"],
    "Value": [rf, ocp_ret, ocp_sd, ocp_sharpe, y_risky, A_RISK_AVERSION, ret_orp, sd_orp],
})
wtab = w_table.copy()
wtab.insert(0, "mu_fwd", list(mu_fwd.values) + [rf])
wtab.insert(1, "hist_mu", list(hist_mu.values) + [np.nan])
wtab.index.name = "Asset"

with pd.ExcelWriter("forward_results.xlsx", engine="openpyxl") as xw:
    sheet = "Forward OCP"
    summary.to_excel(xw, sheet_name=sheet, index=False, startrow=1)
    xw.sheets[sheet].cell(row=1, column=1, value="Forward OCP summary (annualised decimals)")
    r0 = len(summary) + 5
    xw.sheets[sheet].cell(row=r0, column=1, value="Weights and forward expected returns")
    wtab.reset_index().to_excel(xw, sheet_name=sheet, index=False, startrow=r0)
    r1 = r0 + len(wtab) + 4
    xw.sheets[sheet].cell(row=r1, column=1, value="Ridge diagnostics")
    diag.reset_index().rename(columns={"index": "ETF"}).to_excel(
        xw, sheet_name=sheet, index=False, startrow=r1)
    ws = xw.sheets[sheet]
    ws.column_dimensions["A"].width = 30
    for col in "BCDEFGH":
        ws.column_dimensions[col].width = 16

# Final guard: nothing used is dated after the cutoff
for obj, nm in [(px_m, "prices"), (rets, "returns"), (rf_m, "RF"), (feat, "features")]:
    assert_cutoff(obj, nm)
print("\nSaved forward_results.json and forward_results.xlsx (sheet 'Forward OCP').")
print("All data used is dated <= 2024-12-31.")
