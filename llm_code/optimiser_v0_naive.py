# ============================================================
# Portfolio analysis: 10 ETFs, Dec 2020 - Dec 2024 (monthly)
# Google Colab
# ============================================================
!pip install -q yfinance openpyxl

import io, json, zipfile
import numpy as np
import pandas as pd
import requests
import yfinance as yf
from scipy.optimize import minimize

# ------------------------------------------------------------
# 1. Settings
# ------------------------------------------------------------
TICKERS = ["SPY", "IWM", "VEA", "VWO", "XLE", "QQQ", "AGG", "TIP", "HYG", "GLD"]
START, END = "2020-12-01", "2025-01-01"   # END is exclusive, so Dec 2024 is included
A = 7                                      # risk aversion
MAX_W_FALLBACK = 0.95                      # cap used only if ORP collapses into 1 ETF
PERIODS = 12

# ------------------------------------------------------------
# 2. Monthly ETF prices -> monthly returns
# ------------------------------------------------------------
px = yf.download(TICKERS, start=START, end=END, interval="1mo",
                 auto_adjust=True, progress=False)["Close"][TICKERS]
px.index = px.index.to_period("M")
px = px.loc["2020-12":"2024-12"].dropna()
rets = px.pct_change().dropna()            # Jan 2021 ... Dec 2024 (48 months)

# ------------------------------------------------------------
# 3. Risk-free rate (Kenneth French data library, monthly RF in %)
# ------------------------------------------------------------
def get_french_rf():
    url = ("https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
           "F-F_Research_Data_Factors_CSV.zip")
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    text = z.read(z.namelist()[0]).decode("latin-1")
    rows = []
    for line in text.splitlines():
        p = [x.strip() for x in line.split(",")]
        # monthly rows start with YYYYMM; the annual section uses YYYY so it is skipped
        if len(p) >= 5 and p[0].isdigit() and len(p[0]) == 6:
            rows.append((pd.Period(p[0], freq="M"), float(p[4])))
    return pd.Series(dict(rows), name="RF") / 100.0   # percent -> decimal

try:
    rf_m = get_french_rf()
except Exception as e:
    print("Direct download failed, trying pandas_datareader:", e)
    import pandas_datareader.data as web
    rf_m = web.DataReader("F-F_Research_Data_Factors", "famafrench",
                          start="2020-12-01", end="2024-12-31")[0]["RF"] / 100.0
    rf_m.index = rf_m.index.to_period("M")

rf_m = rf_m.reindex(rets.index)
if rf_m.isna().any():
    raise ValueError(f"Missing RF values for: {list(rf_m[rf_m.isna()].index)}")

rf_annual = rf_m.mean() * PERIODS          # annualised average monthly risk-free rate
print(f"Sample: {rets.index[0]} to {rets.index[-1]}  ({len(rets)} monthly returns)")
print(f"Annualised risk-free rate: {rf_annual:.4%}\n")

# ------------------------------------------------------------
# 4. Individual ETF statistics
# ------------------------------------------------------------
excess = rets.sub(rf_m, axis=0)

mu_ann  = rets.mean() * PERIODS
sd_ann  = rets.std(ddof=1) * np.sqrt(PERIODS)
sharpe  = (excess.mean() * PERIODS) / sd_ann

stats = pd.DataFrame({"Ann. Return": mu_ann,
                      "Ann. Std Dev": sd_ann,
                      "Sharpe Ratio": sharpe})
print("=== Individual ETF statistics ===")
print(stats.round(4), "\n")

# Annualised inputs for optimisation
mu  = mu_ann.values
cov = rets.cov().values * PERIODS
n   = len(TICKERS)

def port_stats(w):
    return float(w @ mu), float(np.sqrt(w @ cov @ w))

# ------------------------------------------------------------
# 5. Minimum variance portfolio (long-only, fully invested)
# ------------------------------------------------------------
cons = [{"type": "eq", "fun": lambda w: w.sum() - 1}]
w0 = np.ones(n) / n

res_mvp = minimize(lambda w: w @ cov @ w, w0, method="SLSQP",
                   bounds=[(0, 1)] * n, constraints=cons,
                   options={"ftol": 1e-12, "maxiter": 1000})
w_mvp = np.clip(res_mvp.x, 0, None); w_mvp /= w_mvp.sum()
mvp_ret, mvp_sd = port_stats(w_mvp)

# ------------------------------------------------------------
# 6. Optimal risky portfolio (max Sharpe, no shorting, >= 2 ETFs)
# ------------------------------------------------------------
def neg_sharpe(w):
    r, s = port_stats(w)
    return -(r - rf_annual) / s

def max_sharpe(max_w=1.0):
    best = None
    # multiple starts to avoid local optima
    starts = [w0] + [np.random.default_rng(i).dirichlet(np.ones(n)) for i in range(20)]
    for s0 in starts:
        r = minimize(neg_sharpe, s0, method="SLSQP",
                     bounds=[(0, max_w)] * n, constraints=cons,
                     options={"ftol": 1e-12, "maxiter": 1000})
        if r.success and (best is None or r.fun < best.fun):
            best = r
    w = np.clip(best.x, 0, None)
    return w / w.sum()

w_orp = max_sharpe(1.0)
if (w_orp > 1e-4).sum() < 2:               # enforce at least 2 ETFs
    print(f"Max-Sharpe collapsed into one ETF; re-solving with max weight {MAX_W_FALLBACK:.0%}.\n")
    w_orp = max_sharpe(MAX_W_FALLBACK)
orp_ret, orp_sd = port_stats(w_orp)
orp_sharpe = (orp_ret - rf_annual) / orp_sd

# ------------------------------------------------------------
# 7. Optimal complete portfolio (risk aversion A = 7)
#    y* = (E[r_ORP] - rf) / (A * sigma_ORP^2)
# ------------------------------------------------------------
y_star = (orp_ret - rf_annual) / (A * orp_sd ** 2)
ocp_ret = rf_annual + y_star * (orp_ret - rf_annual)
ocp_sd  = abs(y_star) * orp_sd
w_ocp = y_star * w_orp                      # weights in risky ETFs (rest in risk-free)
w_rf  = 1 - y_star

# ------------------------------------------------------------
# 8. Print results
# ------------------------------------------------------------
weights = pd.DataFrame({"MVP": w_mvp, "ORP": w_orp, "OCP": w_ocp}, index=TICKERS)
weights.loc["Risk-free"] = [0.0, 0.0, w_rf]

summary = pd.DataFrame({
    "Ann. Return":  [mvp_ret, orp_ret, ocp_ret],
    "Ann. Std Dev": [mvp_sd,  orp_sd,  ocp_sd],
    "Sharpe Ratio": [(mvp_ret - rf_annual) / mvp_sd,
                     orp_sharpe,
                     (ocp_ret - rf_annual) / ocp_sd],
}, index=["Minimum Variance (MVP)", "Optimal Risky (ORP)", f"Optimal Complete (OCP, A={A})"])

print("=== Portfolio summary ===")
print(summary.round(4), "\n")
print("=== Portfolio weights ===")
print(weights.round(4), "\n")
print(f"Risk aversion A = {A}: y* (fraction in ORP) = {y_star:.4f}, "
      f"risk-free weight = {w_rf:.4f}")
if y_star > 1:
    print("Note: y* > 1 means the OCP borrows at the risk-free rate to leverage the ORP.")

# ------------------------------------------------------------
# 9. Save to Excel
# ------------------------------------------------------------
xlsx_name = "portfolio_results.xlsx"
with pd.ExcelWriter(xlsx_name, engine="openpyxl") as writer:
    stats.to_excel(writer, sheet_name="ETF Stats")
    summary.to_excel(writer, sheet_name="Portfolios")
    weights.to_excel(writer, sheet_name="Weights")
    pd.DataFrame({"Item": ["Annualised risk-free rate", "Risk aversion (A)", "y* (weight in ORP)"],
                  "Value": [rf_annual, A, y_star]}).to_excel(writer, sheet_name="Inputs", index=False)
    rets.set_axis(rets.index.astype(str)).to_excel(writer, sheet_name="Monthly Returns")
    cov_df = pd.DataFrame(cov, index=TICKERS, columns=TICKERS)
    cov_df.to_excel(writer, sheet_name="Ann. Covariance")
print(f"\nSaved {xlsx_name}")

# ------------------------------------------------------------
# 10. Save results.json (annualised, decimals)
# ------------------------------------------------------------
results = {
    "mvp": {"ret": float(mvp_ret), "sd": float(mvp_sd)},
    "orp": {"ret": float(orp_ret), "sd": float(orp_sd)},
    "ocp": {"ret": float(ocp_ret), "sd": float(ocp_sd)},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)
print("Saved results.json")
print(json.dumps(results, indent=2))

# Optional: download the files from Colab
# from google.colab import files
# files.download(xlsx_name); files.download("results.json")
