# !pip install -q pandas requests   # (already available in Colab; uncomment if needed)

import io
import time

import pandas as pd
import requests

START = pd.Timestamp("2019-01-01")
END = pd.Timestamp("2024-12-31")   # HARD CUT-OFF: nothing after this date is used

BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"

# series_id -> (frequency, why it matters)
SERIES = {
    # 10-year Treasury yield: discount rate; drives bond prices and equity valuations
    "DGS10":    "daily",
    # 10y minus 2y spread: yield-curve slope; recession and growth signal
    "T10Y2Y":   "daily",
    # CBOE VIX: equity risk appetite
    "VIXCLS":   "daily",
    # Effective fed funds rate: policy stance; cost of carry for gold and credit
    "FEDFUNDS": "monthly",
    # CPI all urban consumers: inflation; matters for TIPS, gold, real yields
    "CPIAUCSL": "monthly",
    # Unemployment rate: labour market and growth cycle
    "UNRATE":   "monthly",
}


def download_series(sid: str, retries: int = 3) -> pd.Series:
    """Download one FRED series, restricted to START..END, with '.' treated as missing."""
    # cosd/coed ask FRED to cut the data server-side, so later data is never downloaded
    params = {"id": sid, "cosd": START.strftime("%Y-%m-%d"), "coed": END.strftime("%Y-%m-%d")}
    last_err = None
    for attempt in range(retries):
        try:
            r = requests.get(BASE, params=params, timeout=60)
            r.raise_for_status()
            break
        except Exception as e:  # network hiccup: wait and retry
            last_err = e
            time.sleep(2 * (attempt + 1))
    else:
        raise RuntimeError(f"Could not download {sid}: {last_err}")

    # FRED's date column is 'observation_date' (new) or 'DATE' (old); use position to be safe
    df = pd.read_csv(io.StringIO(r.text), na_values=["."], keep_default_na=True)
    date_col, val_col = df.columns[0], df.columns[1]
    df[date_col] = pd.to_datetime(df[date_col])
    df[val_col] = pd.to_numeric(df[val_col], errors="coerce")

    s = df.set_index(date_col)[val_col].rename(sid).sort_index()
    s = s.dropna()                                  # Rule 1: drop missing values
    s = s[(s.index >= START) & (s.index <= END)]    # Rule 2: local safety filter as well
    return s


# ---------------------------------------------------------------- download
raw = {sid: download_series(sid) for sid in SERIES}

# Rule 2 assert: latest date of every series must be <= 2024-12-31
for sid, s in raw.items():
    assert len(s) > 0, f"{sid}: no data returned"
    assert s.index.max() <= END, f"{sid}: data after {END.date()} found ({s.index.max()})"
    assert s.index.min() >= START, f"{sid}: data before {START.date()} found ({s.index.min()})"

# ---------------------------------------------------------------- month-end conversion
def to_month_end(s: pd.Series, freq: str) -> pd.Series:
    # Roll each date forward to its calendar month-end (a month-end date stays put)
    me = (s.index + pd.offsets.MonthEnd(0)).normalize()
    s = s.copy()
    s.index = me
    if freq == "daily":
        s = s.groupby(level=0).mean()               # Rule 3: monthly mean of daily values
    else:
        s = s.groupby(level=0).last()               # monthly series: value as is
    s.index.name = "date"
    return s


monthly = {sid: to_month_end(raw[sid], freq) for sid, freq in SERIES.items()}

# Common month-end grid so that any missing month shows up as NaN rather than a dropped row
full_index = pd.date_range(START, END, freq="MS") + pd.offsets.MonthEnd(0)
full_index.name = "date"
macro = pd.concat(monthly.values(), axis=1).reindex(full_index)
macro = macro[list(SERIES.keys())]

assert macro.index.max() <= END, "Combined table contains dates after 2024-12-31"

# ---------------------------------------------------------------- save
macro.to_csv("macro.csv")

# ---------------------------------------------------------------- report
pd.set_option("display.width", 140)
pd.set_option("display.max_columns", 20)

print("Last available observation date per series (raw data):")
for sid, s in raw.items():
    print(f"  {sid:9s} {s.index.max().date()}")

print(f"\nNumber of months: {len(macro)} ({macro.index.min().date()} to {macro.index.max().date()})")

print("\nMissing values per column:")
print(macro.isna().sum().to_string())

print("\nFirst 3 rows:")
print(macro.head(3).round(3))
print("\nLast 3 rows:")
print(macro.tail(3).round(3))

est = macro.loc["2021-01-01":"2024-12-31"]
summary = est.agg(["mean", "min", "max"]).T.round(3)
print("\nSummary statistics, 2021-2024 (month-end data):")
print(summary)

print("\nSaved: macro.csv")
