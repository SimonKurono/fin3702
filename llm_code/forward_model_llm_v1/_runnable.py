# =============================================================================
# Forward-looking (2025) macro-driven portfolio selection model
# All information used is dated <= 2024-12-31.
# =============================================================================
import sys, subprocess
subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                "yfinance", "openpyxl", "scikit-learn", "scipy", "pandas", "numpy", "requests"],
               check=False)

import io, re, json, zipfile
import numpy as np
import pandas as pd
import requests
import yfinance as yf
from sklearn.linear_model import RidgeCV, Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.covariance import LedoitWolf
from scipy.optimize import minimize

# ----------------------------------------------------------------------------
# Global settings and hard cut-off
# ----------------------------------------------------------------------------
CUTOFF = pd.Timestamp("2024-12-31")
TICKERS = ["SPY", "IWM", "VEA", "VWO", "XLE", "QQQ", "AGG", "TIP", "HYG", "GLD"]
A_RISK_AVERSION = 7.0
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; research-script)"}
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 50)


def assert_cutoff(obj, name):
    """Hard rule: nothing dated after 2024-12-31 may be used."""
    idx = obj.index if hasattr(obj, "index") else obj
    assert len(idx) > 0, f"{name}: empty"
    assert pd.Timestamp(idx.max()) <= CUTOFF, f"{name}: contains data after {CUTOFF.date()} ({idx.max()})"


def to_month_end(df, how):
    """Aggregate a daily/monthly frame by calendar month, label with calendar month-end."""
    g = df.groupby(df.index.to_period("M"))
    out = g.mean() if how == "mean" else g.last()
    out.index = pd.PeriodIndex(out.index, freq="M").end_time.normalize()
    return out


# ----------------------------------------------------------------------------
# 1. ETF data
# ----------------------------------------------------------------------------
START, END_EXCL = "2020-11-20", "2025-01-01"   # end is exclusive -> last day 2024-12-31
raw = yf.download(TICKERS, start=START, end=END_EXCL, auto_adjust=False,
                  progress=False, group_by="column")
px_daily = raw["Adj Close"][TICKERS].copy()
px_daily.index = pd.to_datetime(px_daily.index).tz_localize(None)
px_daily = px_daily.loc[:CUTOFF]            # defensive
assert_cutoff(px_daily, "daily prices")

px_m = to_month_end(px_daily.dropna(how="all"), "last")
px_m = px_m.loc["2020-12-31":"2024-12-31"]
assert_cutoff(px_m, "monthly prices")
assert px_m.index[0] == pd.Timestamp("2020-12-31") and px_m.index[-1] == pd.Timestamp("2024-12-31")
assert px_m.notna().all().all(), "Missing monthly prices"

rets = px_m / px_m.shift(1) - 1
rets = rets.iloc[1:]
assert len(rets) == 48, f"Expected 48 monthly returns, got {len(rets)}"
assert rets.index[0] == pd.Timestamp("2021-01-31") and rets.index[-1] == pd.Timestamp("2024-12-31")
assert_cutoff(rets, "returns")

# ----------------------------------------------------------------------------
# 2. Risk-free rate (Fama-French)
# ----------------------------------------------------------------------------
FF_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip"
r = requests.get(FF_URL, headers=HEADERS, timeout=60)
r.raise_for_status()
with zipfile.ZipFile(io.BytesIO(r.content)) as z:
    name = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
    text = z.read(name).decode("latin-1")

rf_rows, started = [], False
for line in text.splitlines():
    fields = [f.strip() for f in line.split(",")]
    if re.fullmatch(r"\d{6}", fields[0] or ""):
        started = True
        rf_rows.append((fields[0], float(fields[4])))   # Mkt-RF, SMB, HML, RF
    elif started:
        break                                           # end of monthly table (annual follows)
ff = pd.Series({pd.Timestamp(f"{k[:4]}-{k[4:]}-01") + pd.offsets.MonthEnd(0): v / 100.0
                for k, v in rf_rows}).sort_index()
ff = ff.loc[:CUTOFF]                                    # drop anything dated later immediately
assert_cutoff(ff, "Fama-French RF")
rf_m = ff.loc["2021-01-31":"2024-12-31"]
assert len(rf_m) == 48, f"Expected 48 RF observations, got {len(rf_m)}"
rf = float(rf_m.mean() * 12)
print(f"Annualised risk-free rate rf = {rf:.5f}")

# ----------------------------------------------------------------------------
# 3. Macro data (FRED)
# ----------------------------------------------------------------------------
def fred(series_id):
    url = (f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
           f"&cosd=2019-01-01&coed=2024-12-31")
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text), na_values=["."])
    df.columns = ["date", series_id]
    df["date"] = pd.to_datetime(df["date"])
    s = pd.to_numeric(df[series_id], errors="coerce")
    s.index = df["date"]
    s = s.loc["2019-01-01":"2024-12-31"].dropna().to_frame(series_id)
    assert_cutoff(s, f"FRED {series_id}")
    return s

dgs10 = to_month_end(fred("DGS10"), "mean")["DGS10"]
t10y2y = to_month_end(fred("T10Y2Y"), "mean")["T10Y2Y"]
vix = to_month_end(fred("VIXCLS"), "mean")["VIXCLS"]
ffr = to_month_end(fred("FEDFUNDS"), "last")["FEDFUNDS"]
cpi = to_month_end(fred("CPIAUCSL"), "last")["CPIAUCSL"]
unr = to_month_end(fred("UNRATE"), "last")["UNRATE"]

feat = pd.DataFrame({
    "y10": dgs10,
    "curve": t10y2y,
    "vix": vix,
    "ffr": ffr,
    "cpi_yoy": 100.0 * (cpi / cpi.shift(12) - 1.0),
    "unrate": unr,
})
# Publication delay: CPI and unemployment of month t only known in t+1
feat["cpi_yoy"] = feat["cpi_yoy"].shift(1)
feat["unrate"] = feat["unrate"].shift(1)
feat = feat.loc["2019-01-31":"2024-12-31"]
assert_cutoff(feat, "features")
FEATS = list(feat.columns)

# ----------------------------------------------------------------------------
# 4. Forecasting model: ridge with LOO-CV penalty, features lagged one month
# ----------------------------------------------------------------------------
X_lag = feat.shift(1).reindex(rets.index)           # features known at end of month t-1
x_new = feat.loc[[pd.Timestamp("2024-12-31")]]      # Dec 2024 features -> 2025 forecast
assert not X_lag.isna().any().any(), "NaN in lagged training features"
assert not x_new.isna().any().any(), "NaN in Dec-2024 features"
assert X_lag.index.max() <= CUTOFF and x_new.index.max() <= CUTOFF

alphas = np.logspace(-2, 4, 80)


def loo_r2(X, y, alpha):
    n = len(y)
    pred = np.zeros(n)
    for i in range(n):
        m = np.ones(n, bool)
        m[i] = False
        mdl = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
        mdl.fit(X[m], y[m])
        pred[i] = mdl.predict(X[i:i + 1])[0]
    return 1.0 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2)


Xv = X_lag.values
mu_fwd, coef_tbl, info = {}, {}, []
for tk in TICKERS:
    y = rets[tk].values
    mdl = make_pipeline(StandardScaler(), RidgeCV(alphas=alphas))   # efficient LOO-CV (cv=None)
    mdl.fit(Xv, y)
    ridge = mdl.named_steps["ridgecv"]
    alpha = float(ridge.alpha_)
    r2 = loo_r2(Xv, y, alpha)
    pred_m = float(mdl.predict(x_new.values)[0])
    mu_fwd[tk] = pred_m * 12.0
    coef_tbl[tk] = dict(zip(FEATS, ridge.coef_))
    coef_tbl[tk]["intercept"] = float(ridge.intercept_)
    info.append({"ETF": tk, "alpha": alpha, "LOO_R2": r2, "mu_fwd_annual": mu_fwd[tk]})

info_df = pd.DataFrame(info).set_index("ETF")
coef_df = pd.DataFrame(coef_tbl).T
print("\n=== Ridge models (LOO-CV penalty, standardised features) ===")
print(info_df.to_string(float_format=lambda v: f"{v:,.5f}"))
print("\nCoefficients on standardised features (monthly-return units):")
print(coef_df.to_string(float_format=lambda v: f"{v:,.5f}"))

mu = np.array([mu_fwd[t] for t in TICKERS])
print("\n=== Forward expected annual returns mu_fwd (2025) ===")
print(pd.Series(mu_fwd).to_string(float_format=lambda v: f"{v:,.4%}"))

# ----------------------------------------------------------------------------
# 5. Covariance: Ledoit-Wolf, annualised
# ----------------------------------------------------------------------------
Sigma = LedoitWolf().fit(rets[TICKERS].values).covariance_ * 12.0

# ----------------------------------------------------------------------------
# 6. Portfolios
# ----------------------------------------------------------------------------
n = len(TICKERS)


def neg_sharpe(w):
    var = float(w @ Sigma @ w)
    return -(float(w @ mu) - rf) / np.sqrt(max(var, 1e-14))


rng = np.random.default_rng(42)
starts = [np.ones(n) / n]
starts += [np.eye(n)[i] * 0.6 + 0.4 / n for i in range(n)]
starts += list(rng.dirichlet(np.ones(n), size=15))
assert len(starts) >= 10

cons = ({"type": "eq", "fun": lambda w: np.sum(w) - 1.0},)
bnds = [(0.0, 1.0)] * n
best = None
for w0 in starts:
    res = minimize(neg_sharpe, w0 / w0.sum(), method="SLSQP", bounds=bnds,
                   constraints=cons, options={"maxiter": 1000, "ftol": 1e-12})
    if res.success and (best is None or res.fun < best.fun):
        best = res
if best is None:
    raise RuntimeError("SLSQP failed from all starting points.")

w_orp = np.clip(best.x, 0.0, 1.0)
w_orp = w_orp / w_orp.sum()
if int((w_orp > 1e-4).sum()) < 2:
    raise ValueError("ORP holds fewer than 2 ETFs with weight > 0.0001; "
                     "please choose other ETFs.")

er_orp = float(w_orp @ mu)
var_orp = float(w_orp @ Sigma @ w_orp)
sd_orp = float(np.sqrt(var_orp))
sharpe_orp = (er_orp - rf) / sd_orp
if er_orp - rf <= 0:
    raise ValueError("ORP expected excess return is not positive; the long-only tangency "
                     "portfolio is undefined for this ETF set. Please choose other ETFs.")

# Optimal complete portfolio
y_ocp = (er_orp - rf) / (A_RISK_AVERSION * var_orp)
w_ocp_risky = y_ocp * w_orp
w_rf = 1.0 - y_ocp
ret_ocp = rf + y_ocp * (er_orp - rf)
sd_ocp = y_ocp * sd_orp
sharpe_ocp = (ret_ocp - rf) / sd_ocp

# ----------------------------------------------------------------------------
# 7. Output
# ----------------------------------------------------------------------------
print("\n=== ORP (tangency, long-only) ===")
print(pd.Series(w_orp, index=TICKERS).to_string(float_format=lambda v: f"{v:,.4%}"))
print(f"ORP expected return {er_orp:.4%} | sd {sd_orp:.4%} | Sharpe {sharpe_orp:.4f}")

print(f"\n=== OCP (A = {A_RISK_AVERSION:g}) ===")
ocp_w = pd.Series(list(w_ocp_risky) + [w_rf], index=TICKERS + ["RiskFree"])
print(ocp_w.to_string(float_format=lambda v: f"{v:,.4%}"))
print(f"y = {y_ocp:.4f}")
print(f"OCP expected return {ret_ocp:.4%} | sd {sd_ocp:.4%} | Sharpe {sharpe_ocp:.4f}")

results = {
    "weights": {t: float(w) for t, w in zip(TICKERS, w_ocp_risky)},
    "ret": float(ret_ocp),
    "sd": float(sd_ocp),
    "sharpe": float(sharpe_ocp),
    "y": float(y_ocp),
    "mu_fwd": {t: float(mu_fwd[t]) for t in TICKERS},
}
results["weights"]["RiskFree"] = float(w_rf)

with open("forward_results.json", "w") as f:
    json.dump(results, f, indent=2)

summary = pd.DataFrame({
    "Metric": ["Risk-free rate (rf)", "Risk aversion A", "y (share in ORP)", "OCP expected return",
               "OCP sd", "OCP Sharpe", "ORP expected return", "ORP sd", "ORP Sharpe"],
    "Value": [rf, A_RISK_AVERSION, y_ocp, ret_ocp, sd_ocp, sharpe_ocp, er_orp, sd_orp, sharpe_orp],
})
alloc = pd.DataFrame({
    "Asset": TICKERS + ["RiskFree"],
    "ORP weight": list(w_orp) + [0.0],
    "OCP weight": list(w_ocp_risky) + [w_rf],
    "mu_fwd (annual)": [mu_fwd[t] for t in TICKERS] + [rf],
})
with pd.ExcelWriter("forward_results.xlsx", engine="openpyxl") as xw:
    summary.to_excel(xw, sheet_name="Forward OCP", index=False, startrow=0)
    alloc.to_excel(xw, sheet_name="Forward OCP", index=False, startrow=len(summary) + 3)
    ws = xw.sheets["Forward OCP"]
    ws.column_dimensions["A"].width = 24
    for col in "BCD":
        ws.column_dimensions[col].width = 18

# Final safety check: nothing after cut-off was used
for obj, nm in [(px_m, "px_m"), (rets, "rets"), (rf_m, "rf_m"), (feat, "feat"), (X_lag, "X_lag"), (x_new, "x_new")]:
    assert_cutoff(obj, nm)
print("\nSaved forward_results.json and forward_results.xlsx (all data <= 2024-12-31).")