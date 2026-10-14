import io
import urllib.request
import zipfile

import pandas as pd
import yfinance as yf

from config import (ALL, BASE_DATE, DATA_DIR, PRICE_DIR, FF_URL, FRED_SERIES, HOLD_END,
                    MACRO_CAP, MACRO_START)

_UA = {"User-Agent": "Mozilla/5.0"}


def _month_end(idx):
    return pd.DatetimeIndex(idx).to_period("M").to_timestamp() + pd.offsets.MonthEnd(0)


def load_prices(refresh=False):
    """Month-end (adj close, close), BASE_DATE..HOLD_END. Cached so adjusted
    closes do not drift when Yahoo restates dividends."""
    fa, fc = PRICE_DIR / "prices_adj.csv", PRICE_DIR / "prices_close.csv"
    PRICE_DIR.mkdir(parents=True, exist_ok=True)
    if refresh or not (fa.exists() and fc.exists()):
        px = yf.download(ALL, start="2020-11-20", end="2026-01-10", interval="1d",
                         auto_adjust=False, progress=False)
        for field, f in (("Adj Close", fa), ("Close", fc)):
            m = px[field][ALL].resample("ME").last()
            m = m[(m.index >= BASE_DATE) & (m.index <= HOLD_END)]
            m.to_csv(f)
    read = lambda f: pd.read_csv(f, index_col=0, parse_dates=True)
    return read(fa), read(fc)


def load_french(refresh=False):
    f = DATA_DIR / "french.csv"
    if refresh or not f.exists():
        raw = urllib.request.urlopen(urllib.request.Request(FF_URL, headers=_UA), timeout=60).read()
        z = zipfile.ZipFile(io.BytesIO(raw))
        txt = z.read(z.namelist()[0]).decode()
        rows = [l.split(",") for l in txt.splitlines()
                if len(l.split(",")[0].strip()) == 6 and l.split(",")[0].strip().isdigit()]
        df = pd.DataFrame(rows).iloc[:, :5]
        df.columns = ["ym", "Mkt-RF", "SMB", "HML", "RF"]
        df.index = _month_end(pd.to_datetime(df.pop("ym").str.strip() + "01"))
        df.astype(float).to_csv(f)
    return pd.read_csv(f, index_col=0, parse_dates=True)


def rf_decimal(ff):
    return ff["RF"] / 100.0


def load_macro(refresh=False):
    """FRED series to month-end. Daily series -> monthly mean. Hard-capped at MACRO_CAP."""
    f = DATA_DIR / "macro.csv"
    if refresh or not f.exists():
        cols = {}
        for s in FRED_SERIES:
            d = pd.read_csv(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={s}",
                            na_values=["."], index_col=0, parse_dates=True).iloc[:, 0]
            d = d[MACRO_START:MACRO_CAP].dropna()
            cols[s] = d.resample("ME").mean()
        pd.DataFrame(cols).to_csv(f)
    m = pd.read_csv(f, index_col=0, parse_dates=True)
    return m[m.index <= pd.Timestamp(MACRO_CAP)]
