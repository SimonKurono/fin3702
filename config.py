import os
from pathlib import Path

EQUITY = ["SPY", "IWM", "VEA", "VWO", "XLE", "QQQ"]
BONDS = ["AGG", "TIP", "HYG"]
ALT = ["GLD"]
DEFAULT_ALL = EQUITY + BONDS + ALT

# Use a different set of 10 instruments without editing code:
#   FIN_TICKERS="AAPL,MSFT,..." FIN_BENCHMARK="AAPL" python build_workbook.py
# The benchmark (beta / alpha / information ratio in Step 8) must be one of the 10.
ALL = [t.strip().upper() for t in os.environ["FIN_TICKERS"].split(",") if t.strip()] \
    if os.environ.get("FIN_TICKERS") else list(DEFAULT_ALL)
BENCHMARK = os.environ.get("FIN_BENCHMARK", "SPY" if ALL == DEFAULT_ALL else ALL[0]).strip().upper()
CUSTOM = ALL != DEFAULT_ALL   # True -> the saved LLM outputs (llm_code/) belong to the default 10 and are not used
if len(ALL) != 10 or len(set(ALL)) != 10:
    raise ValueError(f"FIN_TICKERS must list exactly 10 distinct tickers, got {len(ALL)}: {ALL}")
if BENCHMARK not in ALL:
    raise ValueError(f"FIN_BENCHMARK {BENCHMARK!r} must be one of the 10 tickers")

BASE_DATE = "2020-12-31"
EST_START, EST_END = "2021-01-31", "2024-12-31"   # 48 monthly returns
HOLD_START, HOLD_END = "2025-01-31", "2025-12-31"  # Steps 7-8 only
MACRO_START, MACRO_CAP = "2019-01-01", "2024-12-31"
A = 7

DATA_DIR = Path(__file__).parent / "data"
# price cache is per ticker set, so switching portfolios never reads stale prices
PRICE_DIR = DATA_DIR if not CUSTOM else DATA_DIR / ("custom_" + "_".join(sorted(ALL)))
FF_URL = ("https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
          "F-F_Research_Data_Factors_CSV.zip")
FRED_SERIES = ["DGS10", "T10Y2Y", "VIXCLS", "FEDFUNDS", "CPIAUCSL", "UNRATE"]
