# ---- installs (Colab) ----
import subprocess, sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q",
                       "yfinance", "openpyxl", "scipy", "pandas", "numpy", "requests"])

import io, re, json, zipfile
import numpy as np
import pandas as pd
import requests
import yfinance as yf
from scipy.optimize import minimize

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
TICKERS = ["SPY", "IWM", "VEA", "VWO", "XLE", "QQQ", "AGG", "TIP", "HYG", "GLD"]
START, END = "2020-11-20", "2026-01-10"
KEEP_FROM, KEEP_TO = "2020-12-31", "2024-12-31"
FF_URL = ("https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
          "F-F_Research_Data_Factors_CSV.zip")
A_RISK_AVERSION = 7.0
N_STARTS = 25
MIN_W = 1e-4
rng = np.random.default_rng(42)

# ------------------------------------------------------------------
# 1. PRICES
# ------------------------------------------------------------------
raw = yf.download(TICKERS, start=START, end=END, interval="1d",
                  auto_adjust=False, progress=False)
adj = raw["Adj Close"][TICKERS].copy()
adj.index = pd.to_datetime(adj.index).tz_localize(None)
adj = adj.dropna(how="all")

try:
    monthly_px = adj.resample("ME").last()      # newer pandas
except ValueError:
    monthly_px = adj.resample("M").last()       # older pandas
monthly_px = monthly_px.loc[KEEP_FROM:KEEP_TO]

# ------------------------------------------------------------------
# 2. FAMA-FRENCH RF
# ------------------------------------------------------------------
resp = requests.get(FF_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
resp.raise_for_status()
zf = zipfile.ZipFile(io.BytesIO(resp.content))
text = zf.read(zf.namelist()[0]).decode("latin-1")

rf_rows = {}
for line in text.splitlines():
    parts = [p.strip() for p in line.split(",")]
    if len(parts) >= 5 and re.fullmatch(r"\d{6}", parts[0]):
        date = pd.to_datetime(parts[0], format="%Y%m") + pd.offsets.MonthEnd(0)
        rf_rows[date] = float(parts[4]) / 100.0     # columns: date, Mkt-RF, SMB, HML, RF
rf_series = pd.Series(rf_rows, name="RF").sort_index()

# ------------------------------------------------------------------
# 3. RETURNS
# ------------------------------------------------------------------
rets = (monthly_px / monthly_px.shift(1) - 1).dropna(how="all")
rets.index = rets.index.to_period("M").to_timestamp("M")   # normalise to month-end
rets = rets.loc["2021-01-31":"2024-12-31"]
assert rets.shape == (48, len(TICKERS)), f"Expected 48 obs, got {rets.shape}"
assert not rets.isna().any().any(), "NaNs in returns"

rf_m = rf_series.reindex(rets.index)
assert rf_m.notna().all() and len(rf_m) == 48, "RF series misaligned / missing"

# ------------------------------------------------------------------
# STATISTICS
# ------------------------------------------------------------------
rf_ann = float(rf_m.mean() * 12)
mu = rets.mean().values * 12
sd = rets.std(ddof=1).values * np.sqrt(12)
cov = rets.cov().values * 12          # pandas cov is ddof=1
sharpe = (mu - rf_ann) / sd

etf_table = pd.DataFrame({"Ann. Return": mu, "Ann. SD": sd, "Sharpe": sharpe},
                         index=TICKERS)
n = len(TICKERS)

def port_stats(w):
    r = float(w @ mu)
    s = float(np.sqrt(w @ cov @ w))
    return r, s, (r - rf_ann) / s

# ------------------------------------------------------------------
# OPTIMISATION
# ------------------------------------------------------------------
bounds = [(0.0, 1.0)] * n
cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

def starts():
    yield np.ones(n) / n
    for i in range(n):                     # concentrated starts
        w = np.full(n, 0.02); w[i] = 1.0
        yield w / w.sum()
    for _ in range(N_STARTS):
        yield rng.dirichlet(np.ones(n))

def run_opt(obj):
    best = None
    for x0 in starts():
        try:
            res = minimize(obj, x0, method="SLSQP", bounds=bounds,
                           constraints=cons, options={"maxiter": 1000, "ftol": 1e-12})
        except Exception:
            continue
        if not res.success:
            continue
        if best is None or res.fun < best.fun:
            best = res
    if best is None:
        raise RuntimeError("Optimisation failed from all starting points")
    w = np.clip(best.x, 0, 1)
    return w / w.sum()

# a) MVP
w_mvp = run_opt(lambda w: w @ cov @ w)

# b) ORP
def neg_sharpe(w):
    v = w @ cov @ w
    return -((w @ mu - rf_ann) / np.sqrt(max(v, 1e-16)))
w_orp = run_opt(neg_sharpe)
if int((w_orp > MIN_W).sum()) < 2:
    raise ValueError("ORP holds fewer than 2 ETFs with weight > 0.0001. "
                     "Please choose other ETFs.")

# c) OCP
r_orp, s_orp, sh_orp = port_stats(w_orp)
var_orp = s_orp ** 2
y = (r_orp - rf_ann) / (A_RISK_AVERSION * var_orp)
w_ocp_risky = y * w_orp
w_ocp_rf = 1.0 - y
r_ocp = rf_ann + y * (r_orp - rf_ann)
s_ocp = y * s_orp
sh_ocp = (r_ocp - rf_ann) / s_ocp

r_mvp, s_mvp, sh_mvp = port_stats(w_mvp)

# ------------------------------------------------------------------
# OUTPUT
# ------------------------------------------------------------------
pd.set_option("display.width", 200)
print(f"Observations per ETF: {rets.shape[0]}  "
      f"({rets.index[0].date()} to {rets.index[-1].date()})")
print(f"Annualised risk-free rate: {rf_ann:.4%}\n")
print("=== ETF statistics ===")
print(etf_table.to_string(float_format=lambda v: f"{v:.4f}"))

weights_df = pd.DataFrame({"MVP": w_mvp, "ORP": w_orp, "OCP": w_ocp_risky}, index=TICKERS)
weights_df.loc["Risk-free"] = [0.0, 0.0, w_ocp_rf]
perf_df = pd.DataFrame({
    "MVP": [r_mvp, s_mvp, sh_mvp],
    "ORP": [r_orp, s_orp, sh_orp],
    "OCP": [r_ocp, s_ocp, sh_ocp],
}, index=["Ann. Return", "Ann. SD", "Sharpe"])

print("\n=== Portfolio weights ===")
print(weights_df.to_string(float_format=lambda v: f"{v:.4f}"))
print("\n=== Portfolio performance ===")
print(perf_df.to_string(float_format=lambda v: f"{v:.4f}"))
print(f"\nOCP: A = {A_RISK_AVERSION}, y = {y:.4f}, risk-free weight = {w_ocp_rf:.4f}")

# ---- Excel ----
with pd.ExcelWriter("ai_results.xlsx", engine="openpyxl") as xw:
    sheet = "Results"
    row = 0
    pd.DataFrame({"Item": ["Annualised risk-free rate", "Risk aversion A", "y (OCP)",
                           "Observations per ETF"],
                  "Value": [rf_ann, A_RISK_AVERSION, y, rets.shape[0]]}
                 ).to_excel(xw, sheet_name=sheet, startrow=row + 1, index=False)
    xw.sheets[sheet].cell(row=row + 1, column=1, value="Parameters")
    row += 8

    xw.sheets[sheet].cell(row=row + 1, column=1, value="ETF statistics")
    etf_table.to_excel(xw, sheet_name=sheet, startrow=row + 1, index_label="ETF")
    row += len(etf_table) + 4

    xw.sheets[sheet].cell(row=row + 1, column=1, value="Portfolio weights")
    weights_df.to_excel(xw, sheet_name=sheet, startrow=row + 1, index_label="Asset")
    row += len(weights_df) + 4

    xw.sheets[sheet].cell(row=row + 1, column=1, value="Portfolio performance")
    perf_df.to_excel(xw, sheet_name=sheet, startrow=row + 1, index_label="Metric")

    ws = xw.sheets[sheet]
    ws.column_dimensions["A"].width = 28
    for col in "BCDE":
        ws.column_dimensions[col].width = 16

# ---- JSON ----
def wdict(w, extra=None):
    d = {t: float(x) for t, x in zip(TICKERS, w)}
    if extra:
        d.update(extra)
    return d

results = {
    "mvp": {"weights": wdict(w_mvp), "ret": float(r_mvp), "sd": float(s_mvp)},
    "orp": {"weights": wdict(w_orp), "ret": float(r_orp), "sd": float(s_orp)},
    "ocp": {"weights": wdict(w_ocp_risky, {"Risk-free": float(w_ocp_rf)}),
            "ret": float(r_ocp), "sd": float(s_ocp)},
}
with open("results.json", "w") as f:
    json.dump(results, f, indent=2)

print("\nSaved ai_results.xlsx and results.json")
