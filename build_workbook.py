import xlsxwriter
from xlsxwriter.utility import xl_col_to_name as col

import numpy as np

from config import ALL, A
from data import load_french, load_macro, load_prices
from evaluate import holdout_inputs, metrics, wealth
from forward_model import forward_ocp
from optimize import estimation_inputs, frontier, mvp, ocp, orp

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
        "money": wb.add_format({"num_format": "$#,##0"}),
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


def python_solution():
    """Everything the workbook needs from the Python side (decision variables + Step 8)."""
    r, rf_m, st, S, rf = estimation_inputs()
    mu = st["ret"].values
    w_mvp, w_orp = mvp(S.values), orp(mu, S.values, rf)
    o4 = ocp(w_orp, mu, S.values, rf, A)
    fwd = forward_ocp()
    r25, rf25 = holdout_inputs()
    step8 = {}
    for lab, o in (("4c", o4), ("6b", fwd["ocp"])):
        step8[lab] = metrics(wealth(o["w_risky"], o["w_rf"], r25, rf25), rf25, r25["SPY"])
    return {"w_mvp": w_mvp, "w_orp": w_orp, "ocp": o4, "fwd": fwd, "step8": step8,
            "frontier": frontier(mu, S.values, 80), "rf": rf}


def write_solver(wb, ws, f, py):
    ws.set_column("A:A", 30); ws.set_column("B:L", 11)
    ws.write("A1", "Weights via Excel Solver: MVP, ORP, OCP (A = 7)", f["title"])
    ws.write("A2", "Yellow cells are Solver decision variables (pre-filled with the Python optimum). "
                   "Re-run Solver to confirm; everything else is a formula.", f["bold"])
    ws.write("A3", "Ticker", f["hdr"]); ws.write("L3", "Sum", f["hdr"])
    ws.write("A4", "E[r] (annualised)", f["bold"]); ws.write("A5", "St. dev. (annualised)", f["bold"])
    ws.write("A6", "Risk-free (annual)", f["bold"])
    for j, t in enumerate(ALL):
        c = col(1 + j)
        ws.write(f"{c}3", t, f["hdr"])
        ws.write_formula(f"{c}4", f"=S6_Returns!{c}64", f["pct"])
        ws.write_formula(f"{c}5", f"=S6_Returns!{c}65", f["pct"])
        ws.write_number(f"{c}9", float(py["w_mvp"][j]), f["inp"])
        ws.write_number(f"{c}15", float(py["w_orp"][j]), f["inp"])
        ws.write_formula(f"{c}24", f"=$B$23*{c}15", f["num"])
    ws.write_formula("B6", "=S6_Returns!B66", f["pct4"])
    cov = "S7_Cov!$B$2:$K$11"
    ws.write("A8", "1) MINIMUM VARIANCE PORTFOLIO (MVP)", f["hdr"])
    ws.write("A9", "Weights", f["bold"]); ws.write_formula("L9", "=SUM(B9:K9)", f["num"])
    ws.write("A10", "Return", f["bold"]); ws.write_formula("B10", "=SUMPRODUCT(B9:K9,$B$4:$K$4)", f["pct"])
    ws.write("A11", "Variance (objective: minimise)", f["bold"])
    ws.write_formula("B11", f"=SUMPRODUCT(MMULT(B9:K9,{cov}),B9:K9)", f["pct4"])
    ws.write("A12", "St. dev.", f["bold"]); ws.write_formula("B12", "=SQRT(B11)", f["pct"])
    ws.write("A13", "Sharpe", f["bold"]); ws.write_formula("B13", "=(B10-$B$6)/B12", f["num"])
    ws.write("A14", "2) OPTIMUM RISKY PORTFOLIO (ORP)", f["hdr"])
    ws.write("A15", "Weights", f["bold"]); ws.write_formula("L15", "=SUM(B15:K15)", f["num"])
    ws.write("A16", "Return", f["bold"]); ws.write_formula("B16", "=SUMPRODUCT(B15:K15,$B$4:$K$4)", f["pct"])
    ws.write("A17", "Variance", f["bold"])
    ws.write_formula("B17", f"=SUMPRODUCT(MMULT(B15:K15,{cov}),B15:K15)", f["pct4"])
    ws.write("A18", "St. dev.", f["bold"]); ws.write_formula("B18", "=SQRT(B17)", f["pct"])
    ws.write("A19", "Sharpe (objective: maximise)", f["bold"]); ws.write_formula("B19", "=(B16-$B$6)/B18", f["num"])
    ws.write("A20", "# ETFs with weight > 0.01% (need >= 2)", f["bold"])
    ws.write_formula("B20", '=COUNTIF(B15:K15,">0.0001")', f["num"])
    ws.write("A22", "3) OPTIMUM COMPLETE PORTFOLIO (OCP), A = 7", f["hdr"])
    ws.write("A23", "y = share in ORP (decision variable)", f["bold"]); ws.write_number("B23", float(py["ocp"]["y"]), f["inp"])
    ws.write("A24", "Risky weights (y x ORP)", f["bold"])
    ws.write("A25", "Risk-free weight (1 - y; negative = borrowing at rf)", f["bold"])
    ws.write_formula("B25", "=1-B23", f["num"])
    ws.write("A26", "Return", f["bold"]); ws.write_formula("B26", "=$B$6+B23*(B16-$B$6)", f["pct"])
    ws.write("A27", "St. dev.", f["bold"]); ws.write_formula("B27", "=B23*B18", f["pct"])
    ws.write("A28", "Utility = E[r] - 0.5*A*var (objective: maximise)", f["bold"])
    ws.write_formula("B28", "=B26-0.5*B29*B27^2", f["num"])
    ws.write("A29", "Risk aversion A", f["bold"]); ws.write_number("B29", A)
    ws.write("A30", "Closed-form y* = (E[rORP]-rf)/(A var_ORP)", f["bold"])
    ws.write_formula("B30", "=(B16-$B$6)/(B29*B17)", f["num"])
    ws.write("A31", "Sharpe", f["bold"]); ws.write_formula("B31", "=(B26-$B$6)/B27", f["num"])
    steps = [
        "HOW TO RUN SOLVER (Data > Solver; Solving Method = GRG Nonlinear; tick 'Make Unconstrained Variables Non-Negative')",
        "MVP: Set Objective B11 = Min | By Changing B9:K9 | Constraint: L9 = 1",
        "ORP: Set Objective B19 = Max | By Changing B15:K15 | Constraints: L15 = 1 and B20 >= 2",
        "OCP: Set Objective B28 = Max | By Changing B23 | Constraint: B23 >= 0 (B23 > 1 means borrowing at rf)",
        "Check: B23 should equal the closed-form y* in B30. Solver keeps one model per sheet: re-enter the objective for each run.",
    ]
    for i, t in enumerate(steps):
        ws.write(32 + i, 0, t, f["bold"] if i == 0 else None)
    # Best-effort pre-load of the ORP model (Solver stores its model in these sheet-scoped names).
    for name, val in {"solver_opt": "=S8_Solver!$B$19", "solver_typ": "=1", "solver_val": "=0",
                      "solver_adj": "=S8_Solver!$B$15:$K$15", "solver_num": "=2", "solver_eng": "=1",
                      "solver_neg": "=1", "solver_lhs1": "=S8_Solver!$L$15", "solver_rel1": "=2",
                      "solver_rhs1": "=1", "solver_lhs2": "=S8_Solver!$B$20", "solver_rel2": "=3",
                      "solver_rhs2": "=2"}.items():
        wb.define_name(f"S8_Solver!{name}", val)


def write_mvf_chart(wb, ws, f, py):
    fr = py["frontier"]
    ws.set_column("A:A", 14); ws.set_column("B:M", 9)
    ws.write("A1", "Pt", f["hdr"])
    for j, t in enumerate(ALL):
        ws.write(0, 1 + j, t, f["hdr"])
    ws.write("L1", "Return", f["hdr"]); ws.write("M1", "St. dev.", f["hdr"])
    for i in range(len(fr)):
        row = i + 2
        ws.write_number(f"A{row}", i + 1)
        for j in range(N):
            ws.write_number(row - 1, 1 + j, float(fr.iloc[i, 2 + j]), f["num"])  # min-variance weights
        ws.write_formula(f"L{row}", f"=SUMPRODUCT(B{row}:K{row},S8_Solver!$B$4:$K$4)", f["pct"])
        ws.write_formula(f"M{row}", f"=SQRT(SUMPRODUCT(MMULT(B{row}:K{row},S7_Cov!$B$2:$K$11),B{row}:K{row}))", f["pct"])
    last = len(fr) + 1
    base = last + 3                                   # header row of the marker table
    ws.write(f"A{base}", "Point", f["hdr"]); ws.write(f"B{base}", "St. dev.", f["hdr"]); ws.write(f"C{base}", "Return", f["hdr"])
    pts = [("MVP", "=S8_Solver!B12", "=S8_Solver!B10"), ("ORP", "=S8_Solver!B18", "=S8_Solver!B16"),
           ("OCP (A=7)", "=S8_Solver!B27", "=S8_Solver!B26"),
           ("CAL start (rf)", "=0", "=S8_Solver!B6"),
           ("CAL end", "=1.7*S8_Solver!B18", "=S8_Solver!B6+1.7*(S8_Solver!B16-S8_Solver!B6)")]
    for i, (lab, x, y) in enumerate(pts):
        ws.write(f"A{base + 1 + i}", lab); ws.write_formula(f"B{base + 1 + i}", x, f["pct"]); ws.write_formula(f"C{base + 1 + i}", y, f["pct"])
    etf0 = base + 1 + len(pts)
    for j, t in enumerate(ALL):
        c = col(1 + j)
        ws.write(f"A{etf0 + j}", t)
        ws.write_formula(f"B{etf0 + j}", f"=S6_Returns!{c}65", f["pct"]); ws.write_formula(f"C{etf0 + j}", f"=S6_Returns!{c}64", f["pct"])
    ws.write(f"A{etf0 + N + 1}", "Frontier weights (cols B:K) are the min-variance solutions for each target return; "
                                   "return and st. dev. are recomputed from them with Excel formulas.", f["bold"])
    sn = "S2_MVF_Excel"
    ch = wb.add_chart({"type": "scatter", "subtype": "straight"})
    ch.add_series({"name": "Minimum variance frontier", "categories": f"={sn}!$M$2:$M${last}", "values": f"={sn}!$L$2:$L${last}",
                   "line": {"color": "#1F3864", "width": 2.25}, "marker": {"type": "none"}})
    cal = base + 4
    ch.add_series({"name": "Capital allocation line", "categories": f"={sn}!$B${cal}:$B${cal + 1}", "values": f"={sn}!$C${cal}:$C${cal + 1}",
                   "line": {"color": "#C00000", "width": 1.75, "dash_type": "dash"}, "marker": {"type": "none"}})
    for i, (color, size) in enumerate((("#2E7D32", 10), ("#F9A825", 11), ("#6A1B9A", 11))):
        r_ = base + 1 + i
        ch.add_series({"name": f"={sn}!$A${r_}", "categories": f"={sn}!$B${r_}", "values": f"={sn}!$C${r_}",
                       "line": {"none": True}, "marker": {"type": "diamond", "size": size, "fill": {"color": color}, "border": {"color": "black"}},
                       "data_labels": {"series_name": True, "position": "right", "font": {"bold": True}}})
    ch.add_series({"name": "Individual ETFs", "categories": f"={sn}!$B${etf0}:$B${etf0 + N - 1}", "values": f"={sn}!$C${etf0}:$C${etf0 + N - 1}",
                   "line": {"none": True}, "marker": {"type": "circle", "size": 5, "fill": {"color": "#9E9E9E"}, "border": {"color": "#616161"}},
                   "data_labels": {"custom": [{"value": f"={sn}!$A${etf0 + j}"} for j in range(N)], "position": "right", "font": {"size": 8, "color": "#616161"}}})
    ch.set_title({"name": "Minimum Variance Frontier, CAL, MVP / ORP / OCP (A = 7)"})
    ch.set_x_axis({"name": "Annualised standard deviation", "num_format": "0%", "min": 0, "major_gridlines": {"visible": True, "line": {"color": "#E0E0E0"}}})
    ch.set_y_axis({"name": "Annualised return", "num_format": "0%", "major_gridlines": {"visible": True, "line": {"color": "#E0E0E0"}}})
    ch.set_legend({"position": "bottom", "delete_series": [4 + 1]})
    ch.set_size({"width": 980, "height": 600})
    ws.insert_chart("O2", ch)


def write_summary(ws, f, py):
    ws.set_column("A:A", 34); ws.set_column("B:H", 15)
    ws.write("A1", "Executive summary: portfolios, risk and return (estimation window Jan 2021 - Dec 2024, 48 obs)", f["title"])
    heads = ["Asset", "MVP", "ORP", "OCP (Step 4c)", "OCP (Step 6b)", "", "E[r]"]
    for j, h in enumerate(heads):
        if h:
            ws.write(2, j, h, f["hdr"])
    fwd = py["fwd"]["ocp"]
    for j, t in enumerate(ALL):
        row, c = 4 + j, col(1 + j)
        ws.write(f"A{row}", t, f["bold"])
        ws.write_formula(f"B{row}", f"=S8_Solver!{c}9", f["pct"])
        ws.write_formula(f"C{row}", f"=S8_Solver!{c}15", f["pct"])
        ws.write_formula(f"D{row}", f"=S8_Solver!{c}24", f["pct"])
        ws.write_number(f"E{row}", float(fwd["w_risky"][j]), f["inp"])
        ws.write_formula(f"G{row}", f"=S8_Solver!{c}4", f["pct"])
    ws.write("A14", "Risk-free asset (negative = borrowing)", f["bold"])
    ws.write_number("B14", 0, f["pct"]); ws.write_number("C14", 0, f["pct"])
    ws.write_formula("D14", "=S8_Solver!B25", f["pct"]); ws.write_formula("E14", "=1-SUM(E4:E13)", f["pct"])
    ws.write_formula("G14", "=S8_Solver!B6", f["pct"]); ws.write("F14", "rf ->", f["bold"])
    ws.write("A15", "Total", f["bold"])
    cov = "S7_Cov!$B$2:$K$11"
    for x in "BCDE":
        ws.write_formula(f"{x}15", f"=SUM({x}4:{x}14)", f["pct"])
        ws.write_formula(f"{x}17", f"=SUMPRODUCT({x}4:{x}13,$G$4:$G$13)+{x}14*$G$14", f["pct"])
        ws.write_formula(f"{x}18", f"=SQRT(SUMPRODUCT(MMULT({cov},{x}4:{x}13),{x}4:{x}13))", f["pct"])
        ws.write_formula(f"{x}19", f"=({x}17-$G$14)/{x}18", f["num"])
    for row, lab in ((17, "Expected return (annual)"), (18, "St. dev. (annual)"), (19, "Sharpe ratio")):
        ws.write(f"A{row}", lab, f["bold"])
    fo = py["fwd"]["ocp"]
    ws.write("A20", "Step 6b weights (yellow) come from the macro ridge model (forward_model.py). Columns B-E are all evaluated with the same "
                    "2021-24 sample estimates so they are comparable.", None)
    ws.write("A21", f"Step 6b per its own model (macro-ridge E[r], Ledoit-Wolf covariance): return {fo['ret']:.1%}, "
                    f"st. dev. {fo['sd']:.1%}, Sharpe {(fo['ret'] - py['rf']) / fo['sd']:.2f}.", None)
    ws.write("A22", "STEP 8: $100,000 invested at the start of 2025, buy-and-hold (computed in Python: evaluate.py)", f["title"])
    ws.write("D23", "OCP (Step 4c)", f["hdr"]); ws.write("E23", "OCP (Step 6b)", f["hdr"])
    rows = [("End value ($)", "end_value", "money"), ("Total return 2025", "total_return", "pct"), ("Sharpe (annualised)", "sharpe", "num"),
            ("Sortino", "sortino", "num"), ("Treynor", "treynor", "num"), ("Jensen alpha vs SPY", "jensen_alpha", "pct"),
            ("Beta vs SPY", "beta", "num"), ("M-squared", "m2", "pct"), ("Max drawdown", "max_drawdown", "pct"),
            ("Information ratio vs SPY", "info_ratio", "num")]
    for i, (lab, key, kind) in enumerate(rows):
        r_ = 24 + i
        ws.write(f"A{r_}", lab, f["bold"])
        fmt = f[kind]
        ws.write_number(f"D{r_}", py["step8"]["4c"][key], fmt); ws.write_number(f"E{r_}", py["step8"]["6b"][key], fmt)
    ws.write("A35", "Caveat: 48 monthly observations is a small sample; the 12 months of 2025 are even smaller. See the report for sensitivity analysis.", None)


def write_cover(ws, f):
    ws.set_column("A:A", 28); ws.set_column("B:B", 60)
    ws.write("A1", "FIN3702B Investment Analysis & Portfolio Management: Group Project (AY2026/27 Sem 1)", f["title"])
    for i, lab in enumerate(["Section number", "Group number (B#_Group#)"]):
        ws.write(2 + i, 0, lab, f["bold"]); ws.write(2 + i, 1, "", f["inp"])
    ws.write("A6", "Member name", f["hdr"]); ws.write("B6", "Matric number", f["hdr"])
    for i in range(6):
        ws.write(6 + i, 0, "", f["inp"]); ws.write(6 + i, 1, "", f["inp"])
    ws.write("A14", "Colour legend", f["bold"])
    ws.write("A15", "Yellow", f["inp"]); ws.write("B15", "Input or Solver decision variable")
    ws.write("A16", "Navy header", f["hdr"]); ws.write("B16", "Label")
    ws.write("A17", "White"); ws.write("B17", "Formula (no hardcoded results in Sheets 6, 7, 8)")
    ws.write("A19", "Sheet index", f["bold"])
    idx = [("S1_Summary", "Portfolio mix, return, st. dev., Sharpe for MVP, ORP, OCP (4c and 6b); Step 8"),
           ("S2_MVF_Excel", "Minimum variance frontier chart built in Excel (with CAL, MVP, ORP, OCP)"),
           ("S3_MVF_AI", "Same chart generated by LLM-written Python"),
           ("S4_Prices", "Raw monthly ETF prices (Adj Close and Close)"),
           ("S5_Macro", "Fama-French data and FRED macro data"),
           ("S6_Returns", "Monthly returns, annualised return, st. dev., Sharpe (Excel formulas)"),
           ("S7_Cov", "Annualised covariance matrix (Excel formulas)"),
           ("S8_Solver", "Solver derivation of MVP, ORP, OCP")]
    for i, (a, b) in enumerate(idx):
        ws.write(19 + i, 0, a); ws.write(19 + i, 1, b)
    notes = ["Conventions: monthly adjusted close; Dec 2020 base so 48 returns Jan 2021 - Dec 2024; annualised return = mean x 12; "
             "st. dev. = STDEV.S x SQRT(12); rf = French RF/100, mean x 12; no short-selling; ORP needs >= 2 ETFs; A = 7.",
             "Data: Yahoo Finance (prices), Kenneth French Data Library (RF), FRED (macro, capped at Dec 2024 for the Step 6 model).",
             "Caveat: 48 observations is a small sample; weights are sensitive to estimation error (see report)."]
    for i, t in enumerate(notes):
        ws.write(29 + i, 0, t)


def build(path):
    wb = xlsxwriter.Workbook(path, {"use_future_functions": True})
    f = _formats(wb)
    ws = {name: wb.add_worksheet(name) for name in SHEETS}   # creation order fixes sheet order
    write_prices(ws["S4_Prices"], f); write_macro(ws["S5_Macro"], f)
    write_returns(ws["S6_Returns"], f); write_cov(ws["S7_Cov"], f)
    py = python_solution()
    write_solver(wb, ws["S8_Solver"], f, py); write_mvf_chart(wb, ws["S2_MVF_Excel"], f, py)
    write_summary(ws["S1_Summary"], f, py); write_cover(ws["Cover"], f)
    ws["S3_MVF_AI"].write("A1", "Chart generated by LLM-written Python: inserted after the prompts are finalised.", f["title"])
    wb.close()


if __name__ == "__main__":
    build("FIN3702B_Portfolio.xlsx")
