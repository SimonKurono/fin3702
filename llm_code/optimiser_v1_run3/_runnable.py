# !pip install -q yfinance openpyxl scipy pandas numpy requests

import io
import json
import zipfile

import numpy as np
import pandas as pd
import requests
import yfinance as yf
from scipy.optimize import minimize

# ----------------------------------------------------------------------------
# 1. DATA: ETF prices
# ----------------------------------------------------------------------------
TICKERS = ["SPY", "IWM", "VEA", "VWO", "XLE", "QQQ", "AGG", "TIP", "HYG", "GLD"]
A_RISK_AVERSION = 7.0

raw = yf.download(TICKERS, start="2020-11-20", end="2026-01-10",
                  auto_adjust=False, progress=False)
adj = raw["Adj Close"][TICKERS].dropna(how="all")

# Month-end using the LAST available trading day of each month
adj.index = pd.to_datetime(adj.index)
monthly = adj.groupby(adj.index.to_period("M")).last()
monthly.index = monthly.index.to_timestamp(how="end").normalize()  # calendar month-end
monthly = monthly.loc["2020-12-31":"2024-12-31"]

# Simple monthly returns
rets = (monthly / monthly.shift(1) - 1).dropna()
assert rets.shape == (48, len(TICKERS)), f"Expected 48 obs per ETF, got {rets.shape}"
assert rets.index[0] == pd.Timestamp("2021-01-31") and rets.index[-1] == pd.Timestamp("2024-12-31")
assert not rets.isna().any().any()

# ----------------------------------------------------------------------------
# 2. DATA: Fama-French risk-free rate
# ----------------------------------------------------------------------------
FF_URL = ("https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
          "F-F_Research_Data_Factors_CSV.zip")
resp = requests.get(FF_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
resp.raise_for_status()
with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
    name = [n for n in zf.namelist() if n.lower().endswith(".csv")][0]
    text = zf.read(name).decode("latin-1")

rf_dict = {}
for line in text.splitlines():
    parts = [p.strip() for p in line.split(",")]
    # monthly table only: first field is a 6-digit YYYYMM
    if len(parts) >= 5 and len(parts[0]) == 6 and parts[0].isdigit():
        period = pd.Period(parts[0], freq="M")
        rf_dict[period.to_timestamp(how="end").normalize()] = float(parts[4]) / 100.0  # RF in percent
rf_series = pd.Series(rf_dict).sort_index()
rf_m = rf_series.reindex(rets.index)
assert rf_m.notna().all() and len(rf_m) == 48, "Risk-free data missing for some months"

# ----------------------------------------------------------------------------
# 3. STATISTICS
# ----------------------------------------------------------------------------
rf_ann = rf_m.mean() * 12
mu = rets.mean().values * 12                       # annualised arithmetic mean returns
sd = rets.std(ddof=1).values * np.sqrt(12)         # annualised sd
cov = rets.cov(ddof=1).values * 12                 # annualised covariance
sharpe = (mu - rf_ann) / sd

etf_table = pd.DataFrame({"Ann. Return": mu, "Ann. SD": sd, "Sharpe": sharpe}, index=TICKERS)

def port_stats(w):
    r = float(w @ mu)
    v = float(w @ cov @ w)
    s = np.sqrt(v)
    return r, s, (r - rf_ann) / s

# ----------------------------------------------------------------------------
# 4. OPTIMISATION (SLSQP, long-only, fully invested, multi-start)
# ----------------------------------------------------------------------------
n = len(TICKERS)
bounds = [(0.0, 1.0)] * n
cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

rng = np.random.default_rng(42)
starts = [np.ones(n) / n]
starts += [np.eye(n)[i] * 0.8 + 0.2 / n for i in range(n)]       # near-vertex starts
starts += [rng.dirichlet(np.ones(n)) for _ in range(20)]         # random starts
starts = [s / s.sum() for s in starts]

def run_opt(obj):
    best = None
    for x0 in starts:
        try:
            res = minimize(obj, x0, method="SLSQP", bounds=bounds, constraints=cons,
                           options={"maxiter": 1000, "ftol": 1e-12})
        except Exception:
            continue
        if not res.success:
            continue
        if best is None or res.fun < best.fun:
            best = res
    if best is None:
        raise RuntimeError("Optimisation failed for all starting points")
    w = np.clip(best.x, 0, 1)
    return w / w.sum()

# a) MVP
w_mvp = run_opt(lambda w: w @ cov @ w)

# b) ORP (maximise Sharpe)
def neg_sharpe(w):
    v = w @ cov @ w
    return -((w @ mu - rf_ann) / np.sqrt(max(v, 1e-16)))

w_orp = run_opt(neg_sharpe)
w_orp[w_orp < 1e-10] = 0.0
w_orp = w_orp / w_orp.sum()
if int((w_orp > 0.0001).sum()) < 2:
    raise ValueError("ORP holds fewer than 2 ETFs with weight > 0.0001. "
                     "Please choose other ETFs.")

# c) OCP
r_orp, sd_orp, sh_orp = port_stats(w_orp)
var_orp = sd_orp ** 2
y = (r_orp - rf_ann) / (A_RISK_AVERSION * var_orp)
w_ocp_risky = y * w_orp
w_rf = 1.0 - y                                   # negative if y > 1 (borrowing)
r_ocp = rf_ann + y * (r_orp - rf_ann)
sd_ocp = y * sd_orp
sh_ocp = (r_ocp - rf_ann) / sd_ocp

r_mvp, sd_mvp, sh_mvp = port_stats(w_mvp)

# ----------------------------------------------------------------------------
# 5. OUTPUT
# ----------------------------------------------------------------------------
weights_table = pd.DataFrame({
    "MVP": list(w_mvp) + [0.0],
    "ORP": list(w_orp) + [0.0],
    "OCP": list(w_ocp_risky) + [w_rf],
}, index=TICKERS + ["Risk-free"])

summary_table = pd.DataFrame({
    "MVP": [r_mvp, sd_mvp, sh_mvp],
    "ORP": [r_orp, sd_orp, sh_orp],
    "OCP": [r_ocp, sd_ocp, sh_ocp],
}, index=["Ann. Return", "Ann. SD", "Sharpe"])

pd.set_option("display.float_format", lambda v: f"{v:,.4f}")
pd.set_option("display.width", 200)
print(f"Annualised risk-free rate: {rf_ann:.4%}   |   Observations: {len(rets)}")
print(f"Complete-portfolio risky share y (A={A_RISK_AVERSION:g}): {y:.4f}\n")
print("=== Individual ETFs ===")
print(etf_table, "\n")
print("=== Portfolio weights ===")
print(weights_table, "\n")
print("=== Portfolio statistics ===")
print(summary_table)

# Excel
with pd.ExcelWriter("ai_results.xlsx", engine="openpyxl") as writer:
    row = 0
    pd.DataFrame({"Item": ["Annualised risk-free rate", "Risk aversion A",
                           "OCP risky share y", "Observations"],
                  "Value": [rf_ann, A_RISK_AVERSION, y, len(rets)]}
                 ).to_excel(writer, sheet_name="Results", index=False, startrow=row)
    row += 7
    ws = writer.sheets["Results"]
    for title, tbl in [("Individual ETFs", etf_table),
                       ("Portfolio weights", weights_table),
                       ("Portfolio statistics", summary_table)]:
        ws.cell(row=row, column=1, value=title)
        tbl.to_excel(writer, sheet_name="Results", startrow=row)
        row += len(tbl) + 4
    ws.column_dimensions["A"].width = 28
    for col in "BCDE":
        ws.column_dimensions[col].width = 14

# JSON
def wdict(w, extra=None):
    d = {t: float(x) for t, x in zip(TICKERS, w)}
    if extra is not None:
        d["Risk-free"] = float(extra)
    return d

results = {
    "mvp": {"weights": wdict(w_mvp), "ret": float(r_mvp), "sd": float(sd_mvp)},
    "orp": {"weights": wdict(w_orp), "ret": float(r_orp), "sd": float(sd_orp)},
    "ocp": {"weights": wdict(w_ocp_risky, w_rf), "ret": float(r_ocp), "sd": float(sd_ocp)},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print("\nSaved ai_results.xlsx and results.json")