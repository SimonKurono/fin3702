# ============================================================
# Install (Colab):  pip install yfinance openpyxl xlsxwriter
# ============================================================
import subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "yfinance", "openpyxl", "xlsxwriter", "requests"], check=False)

import io, json, zipfile
import numpy as np
import pandas as pd
import requests
import yfinance as yf
from scipy.optimize import minimize

np.set_printoptions(suppress=True, precision=6)
pd.set_option("display.width", 200)
pd.set_option("display.float_format", lambda x: f"{x:,.4f}")

TICKERS = ["SPY", "IWM", "VEA", "VWO", "XLE", "QQQ", "AGG", "TIP", "HYG", "GLD"]
START_DL, END_DL = "2020-11-20", "2026-01-10"
FIRST_ME, LAST_ME = pd.Period("2020-12", "M"), pd.Period("2024-12", "M")
A = 7.0
FF_URL = ("https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
          "F-F_Research_Data_Factors_CSV.zip")

# ------------------------------------------------------------
# 1. Prices: daily adjusted close -> last trading day of each month
# ------------------------------------------------------------
raw = yf.download(TICKERS, start=START_DL, end=END_DL, auto_adjust=False,
                  progress=False)
adj = raw["Adj Close"][TICKERS].copy()
if getattr(adj.index, "tz", None) is not None:
    adj.index = adj.index.tz_localize(None)
adj = adj.dropna(how="all").sort_index()

# last available trading day within each calendar month
monthly = adj.groupby(adj.index.to_period("M")).last()
monthly = monthly.loc[FIRST_ME:LAST_ME]
monthly.index = monthly.index.to_timestamp(how="end").normalize()  # calendar month-end label
if monthly.isna().any().any():
    raise ValueError("Missing monthly prices:\n" + str(monthly.isna().sum()))

# ------------------------------------------------------------
# 2. Fama-French monthly RF (percent -> decimal)
# ------------------------------------------------------------
resp = requests.get(FF_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
resp.raise_for_status()
with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
    name = [n for n in zf.namelist() if n.lower().endswith(".csv")][0]
    text = zf.read(name).decode("latin-1")

rf_rows = {}
for line in text.splitlines():
    parts = [p.strip() for p in line.split(",")]
    if len(parts) >= 5 and len(parts[0]) == 6 and parts[0].isdigit():
        # columns: YYYYMM, Mkt-RF, SMB, HML, RF
        per = pd.Period(parts[0], "M")
        rf_rows[per] = float(parts[4]) / 100.0
rf_series = pd.Series(rf_rows).sort_index()
rf_series.index = rf_series.index.to_timestamp(how="end").normalize()

# ------------------------------------------------------------
# 3. Simple monthly returns
# ------------------------------------------------------------
rets = (monthly / monthly.shift(1) - 1.0).dropna()
assert rets.shape[0] == 48, f"Expected 48 monthly returns, got {rets.shape[0]}"
assert rets.index[0] == pd.Timestamp("2021-01-31") and rets.index[-1] == pd.Timestamp("2024-12-31")

rf_m = rf_series.reindex(rets.index)
if rf_m.isna().any():
    raise ValueError("Risk-free data missing for some months:\n" + str(rf_m[rf_m.isna()]))
assert len(rf_m) == 48

# ------------------------------------------------------------
# Statistics
# ------------------------------------------------------------
mu = rets.mean() * 12.0                       # annualised arithmetic mean return
sd = rets.std(ddof=1) * np.sqrt(12.0)         # annualised sample sd
rf = float(rf_m.mean() * 12.0)                # annualised risk-free rate
cov = rets.cov() * 12.0                       # annualised sample covariance (ddof=1)
sharpe = (mu - rf) / sd

mu_v = mu.values
cov_v = cov.values
n = len(TICKERS)

etf_table = pd.DataFrame({"Ann. Return": mu, "Ann. SD": sd, "Sharpe": sharpe})
print("Annualised risk-free rate: %.4f%%" % (rf * 100))
print("\n=== Individual ETFs ===")
print(etf_table)

# ------------------------------------------------------------
# Optimisation helpers
# ------------------------------------------------------------
def port_ret(w): return float(w @ mu_v)
def port_var(w): return float(w @ cov_v @ w)
def port_sd(w):  return float(np.sqrt(max(port_var(w), 0.0)))
def port_sharpe(w): return (port_ret(w) - rf) / port_sd(w)

rng = np.random.default_rng(42)

def starting_points(k_random=30):
    pts = [np.full(n, 1.0 / n)]
    pts += [np.eye(n)[i] for i in range(n)]                     # single-asset starts
    pts += [rng.dirichlet(np.ones(n)) for _ in range(k_random)]  # random starts
    return pts

CONS = ({"type": "eq", "fun": lambda w: np.sum(w) - 1.0},)
BNDS = [(0.0, 1.0)] * n

def run_opt(objective, tag):
    best = None
    for x0 in starting_points():
        try:
            res = minimize(objective, x0, method="SLSQP", bounds=BNDS, constraints=CONS,
                           options={"maxiter": 1000, "ftol": 1e-12})
        except Exception:
            continue
        if not res.success or not np.all(np.isfinite(res.x)):
            continue
        w = np.clip(res.x, 0.0, 1.0)
        w = w / w.sum()
        val = objective(w)
        if best is None or val < best[0]:
            best = (val, w)
    if best is None:
        raise RuntimeError(f"{tag}: optimisation failed from every starting point")
    return best[1]

# a) MVP
w_mvp = run_opt(port_var, "MVP")

# b) ORP
w_orp = run_opt(lambda w: -port_sharpe(w), "ORP")
w_orp = np.where(w_orp < 1e-10, 0.0, w_orp)
w_orp = w_orp / w_orp.sum()
if int(np.sum(w_orp > 0.0001)) < 2:
    raise ValueError("ORP holds fewer than 2 ETFs with weight > 0.0001. "
                     "Please choose other ETFs.")

# c) OCP, A = 7
ret_orp, var_orp, sd_orp = port_ret(w_orp), port_var(w_orp), port_sd(w_orp)
y = (ret_orp - rf) / (A * var_orp)
w_ocp_risky = y * w_orp
w_ocp_rf = 1.0 - y                      # negative if y > 1 (borrowing at rf)
ret_ocp = rf + y * (ret_orp - rf)
sd_ocp = y * sd_orp

def pack(w, r, s, extra=None):
    return {"weights": {t: float(x) for t, x in zip(TICKERS, w)},
            "ret": float(r), "sd": float(s)}

results = {
    "mvp": pack(w_mvp, port_ret(w_mvp), port_sd(w_mvp)),
    "orp": pack(w_orp, ret_orp, sd_orp),
    "ocp": pack(w_ocp_risky, ret_ocp, sd_ocp),
}
results["ocp"]["weights"]["RiskFree"] = float(w_ocp_rf)

# ------------------------------------------------------------
# Output tables
# ------------------------------------------------------------
def sharpe_of(r, s): return (r - rf) / s

summary = pd.DataFrame({
    "Ann. Return": [results[k]["ret"] for k in ("mvp", "orp", "ocp")],
    "Ann. SD":     [results[k]["sd"] for k in ("mvp", "orp", "ocp")],
    "Sharpe":      [sharpe_of(results[k]["ret"], results[k]["sd"]) for k in ("mvp", "orp", "ocp")],
}, index=["MVP", "ORP", "OCP"])

weights_df = pd.DataFrame({
    "MVP": pd.Series(results["mvp"]["weights"]),
    "ORP": pd.Series(results["orp"]["weights"]),
    "OCP": pd.Series(results["ocp"]["weights"]),
}).reindex(TICKERS + ["RiskFree"])
weights_df.loc["RiskFree", ["MVP", "ORP"]] = 0.0

print("\n=== Portfolio weights ===")
print(weights_df)
print("\n=== Portfolio performance ===")
print(summary)
print(f"\nORP: {int((w_orp > 0.0001).sum())} ETFs with weight > 0.0001")
print(f"OCP (A={A:g}): y = {y:.4f}, risk-free weight = {w_ocp_rf:.4f}"
      + ("  (borrowing at rf)" if y > 1 else ""))

# ------------------------------------------------------------
# Excel: one worksheet "Results"
# ------------------------------------------------------------
with pd.ExcelWriter("ai_results.xlsx", engine="openpyxl") as xw:
    sheet = "Results"
    row = 0
    pd.DataFrame({"Item": ["Annualised risk-free rate", "Risk aversion A", "OCP y (risky share)",
                           "Monthly observations"],
                  "Value": [rf, A, y, 48]}).to_excel(xw, sheet_name=sheet, startrow=row, index=False)
    row += 7
    etf_table.to_excel(xw, sheet_name=sheet, startrow=row + 1, index_label="ETF")
    xw.sheets[sheet].cell(row=row + 1, column=1, value="Individual ETFs")
    row += len(etf_table) + 4
    weights_df.to_excel(xw, sheet_name=sheet, startrow=row + 1, index_label="Asset")
    xw.sheets[sheet].cell(row=row + 1, column=1, value="Portfolio weights")
    row += len(weights_df) + 4
    summary.to_excel(xw, sheet_name=sheet, startrow=row + 1, index_label="Portfolio")
    xw.sheets[sheet].cell(row=row + 1, column=1, value="Portfolio performance")
    ws = xw.sheets[sheet]
    ws.column_dimensions["A"].width = 30
    for col in "BCDE":
        ws.column_dimensions[col].width = 16

with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print("\nSaved ai_results.xlsx and results.json")
