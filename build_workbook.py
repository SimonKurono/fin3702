import xlsxwriter
from xlsxwriter.utility import xl_col_to_name as col

from config import ALL, A
from data import load_french, load_macro, load_prices

N = len(ALL)  # 10
SHEETS = ["Cover", "S1_Summary", "S2_MVF_Excel", "S3_MVF_AI", "S4_Prices",
          "S5_Macro", "S6_Returns", "S7_Cov", "S8_Solver"]


def _formats(wb):
    return {
        "hdr": wb.add_format({"bold": True, "bg_color": "#1F3864", "font_color": "white", "align": "center"}),
        "date": wb.add_format({"num_format": "mmm-yyyy"}),
        "px": wb.add_format({"num_format": "0.00"}),
        "pct": wb.add_format({"num_format": "0.00%"}),
        "pct4": wb.add_format({"num_format": "0.0000%"}),
        "num": wb.add_format({"num_format": "0.0000"}),
        "inp": wb.add_format({"num_format": "0.0000", "bg_color": "#FFF2CC", "border": 1}),
        "bold": wb.add_format({"bold": True}),
        "title": wb.add_format({"bold": True, "font_size": 14}),
    }


def write_prices(ws, f):
    adj, close = load_prices()
    ws.write(0, 0, "Date", f["hdr"])
    for j, t in enumerate(ALL):
        ws.write(0, 1 + j, t, f["hdr"]); ws.write(0, 13 + j, t, f["hdr"])
    ws.write(0, 12, "Close ->", f["bold"])
    for i, d in enumerate(adj.index):
        ws.write_datetime(1 + i, 0, d.to_pydatetime(), f["date"])
        for j, t in enumerate(ALL):
            ws.write_number(1 + i, 1 + j, float(adj.iloc[i, j]), f["px"])
            ws.write_number(1 + i, 13 + j, float(close.iloc[i, j]), f["px"])
    ws.write(63, 0, "Source: Yahoo Finance via yfinance, month-end Adj Close (cols B:K) and Close (cols N:W).", f["bold"])
    ws.freeze_panes(1, 1)


def write_macro(ws, f):
    ff, m = load_french(), load_macro()
    ff = ff["2020-12-31":"2025-12-31"]
    for j, h in enumerate(["Date", "Mkt-RF (%)", "SMB (%)", "HML (%)", "RF (%)"]):
        ws.write(0, j, h, f["hdr"])
    for i, (d, row) in enumerate(ff.iterrows()):
        ws.write_datetime(1 + i, 0, d.to_pydatetime(), f["date"])
        for j, v in enumerate(row.values):
            ws.write_number(1 + i, 1 + j, float(v), f["num"])
    ws.write(len(ff) + 2, 0, "Source: Kenneth French Data Library, F-F_Research_Data_Factors (monthly), percent.", f["bold"])
    ws.write(0, 7, "Date", f["hdr"])
    for j, c in enumerate(m.columns):
        ws.write(0, 8 + j, c, f["hdr"])
    for i, (d, row) in enumerate(m.iterrows()):
        ws.write_datetime(1 + i, 7, d.to_pydatetime(), f["date"])
        for j, v in enumerate(row.values):
            if v == v:
                ws.write_number(1 + i, 8 + j, float(v), f["num"])
    ws.write(len(m) + 2, 7, "Source: FRED (daily series averaged to month); capped at 2024-12-31 for the Step 6 model.", f["bold"])


def write_returns(ws, f):
    ws.write(0, 0, "Date", f["hdr"])
    for j, t in enumerate(ALL):
        ws.write(0, 1 + j, t, f["hdr"])
    ws.write(0, 11, "RF (monthly)", f["hdr"])
    adj, _ = load_prices()
    for i in range(60):                      # Jan 2021 .. Dec 2025 -> sheet rows 2..61
        r = i + 2                            # excel row of this return
        ws.write_datetime(i + 1, 0, adj.index[i + 1].to_pydatetime(), f["date"])
        for j in range(N):
            c = col(1 + j)
            ws.write_formula(i + 1, 1 + j, f"=S4_Prices!{c}{r + 1}/S4_Prices!{c}{r}-1", f["pct"])
        ws.write_formula(i + 1, 11, f"=S5_Macro!E{r + 1}/100", f["pct4"])
    labels = {63: "Annualised return (arith. mean x 12)", 64: "Annualised st. dev. (STDEV.S x SQRT 12)",
              65: "Risk-free (annual, mean monthly RF x 12)", 66: "Sharpe ratio"}
    for row, text in labels.items():
        ws.write(row, 0, text, f["bold"])
    for j in range(N):
        c = col(1 + j)
        ws.write_formula(63, 1 + j, f"=AVERAGE({c}2:{c}49)*12", f["pct"])
        ws.write_formula(64, 1 + j, f"=STDEV.S({c}2:{c}49)*SQRT(12)", f["pct"])
        ws.write_formula(66, 1 + j, f"=({c}64-$B$66)/{c}65", f["num"])
    ws.write_formula(65, 1, "=AVERAGE(L2:L49)*12", f["pct4"])
    ws.write(68, 0, "Estimation window: rows 2-49 (Jan 2021 - Dec 2024, 48 obs). Rows 50-61 (2025) are hold-out, used only in Step 8.", f["bold"])
    ws.freeze_panes(1, 1)


def write_cov(ws, f):
    ws.write(0, 0, "Annualised cov (monthly COVARIANCE.S x 12)", f["hdr"])
    for j, t in enumerate(ALL):
        ws.write(0, 1 + j, t, f["hdr"]); ws.write(1 + j, 0, t, f["hdr"])
    rng = "S6_Returns!$B$2:$K$49"
    for i in range(N):
        for j in range(N):
            ws.write_formula(1 + i, 1 + j,
                f"=COVARIANCE.S(INDEX({rng},0,ROW()-1),INDEX({rng},0,COLUMN()-1))*12", f["num"])


def build(path):
    wb = xlsxwriter.Workbook(path, {"use_future_functions": True})
    f = _formats(wb)
    ws = {name: wb.add_worksheet(name) for name in SHEETS}   # creation order fixes sheet order
    write_prices(ws["S4_Prices"], f); write_macro(ws["S5_Macro"], f)
    write_returns(ws["S6_Returns"], f); write_cov(ws["S7_Cov"], f)
    wb.close()


if __name__ == "__main__":
    build("FIN3702B_Portfolio.xlsx")
