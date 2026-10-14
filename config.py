from pathlib import Path

EQUITY = ["SPY", "IWM", "VEA", "VWO", "XLE", "QQQ"]
BONDS = ["AGG", "TIP", "HYG"]
ALT = ["GLD"]
ALL = EQUITY + BONDS + ALT

BASE_DATE = "2020-12-31"
EST_START, EST_END = "2021-01-31", "2024-12-31"   # 48 monthly returns
HOLD_START, HOLD_END = "2025-01-31", "2025-12-31"  # Steps 7-8 only
MACRO_START, MACRO_CAP = "2019-01-01", "2024-12-31"
A = 7

DATA_DIR = Path(__file__).parent / "data"
FF_URL = ("https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
          "F-F_Research_Data_Factors_CSV.zip")
FRED_SERIES = ["DGS10", "T10Y2Y", "VIXCLS", "FEDFUNDS", "CPIAUCSL", "UNRATE"]
