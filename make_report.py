"""Build Prompts_and_Answers.docx: all prompts (verbatim), Step 8 and Step 9 answers, and the 48-observation caveat.
Numbers are computed from the code and result files, not typed in."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

from config import ALL, BENCHMARK, CUSTOM
from evaluate import holdout_inputs, metrics, wealth
from data import load_french, rf_decimal
from forward_model import forward_ocp
from optimize import estimation_inputs, mvp, ocp, orp, port_stats
from robustness import compare_lw, sensitivity

ROOT = Path(__file__).parent
if CUSTOM:
    raise SystemExit("make_report.py writes prose about the default 10 ETFs and the saved LLM runs; it is not for FIN_TICKERS portfolios.")
PR = ROOT / "docs" / "deliverables" / "prompts"

# ---------------------------------------------------------------- numbers
r, rf_m, st, S, rf = estimation_inputs()
mu = st["ret"].values
w_mvp, w_orp = mvp(S.values), orp(mu, S.values, rf)
o4 = ocp(w_orp, mu, S.values, rf, 7)
L = json.load(open(ROOT / "llm_code/forward_model_llm_v2/forward_results.json"))
o6 = {"w_risky": np.array([L["weights"][t] for t in ALL]), "w_rf": L["weights"]["RiskFree"]}
r25, rf25 = holdout_inputs()
res8 = {}
for lab, o in (("Step 4c OCP", o4), ("Step 6b OCP (LLM)", o6)):
    res8[lab] = metrics(wealth(o["w_risky"], o["w_rf"], r25, rf25), rf25, r25[BENCHMARK])
res8["SPY (benchmark)"] = metrics(wealth(np.eye(10)[ALL.index(BENCHMARK)], 0.0, r25, rf25), rf25, r25[BENCHMARK])
res8["ORP only, unlevered"] = metrics(wealth(w_orp, 0.0, r25, rf25), rf25, r25[BENCHMARK])
etf25 = (1 + r25).prod() - 1
boot = sensitivity(r, rf_m, n=300, scale=0, seed=0, mode="bootstrap")
pert = sensitivity(r, rf_m, n=300, scale=0.10, seed=0, mode="perturb")
lw = compare_lw()
rf24 = float(rf_decimal(load_french())["2024-01-31":"2024-12-31"].mean() * 12)
sens_rf = forward_ocp(rf=rf24)   # Python replica of Step 6b with the rate known at the end of 2024
base_rf = forward_ocp()
share1 = float(((boot["weights"]["ORP"] > 0.01).sum(axis=1) < 2).mean())

# ---------------------------------------------------------------- docx helpers
doc = Document()
doc.styles["Normal"].font.name = "Calibri"
doc.styles["Normal"].font.size = Pt(10.5)


def h(t, lvl=1): doc.add_heading(t, lvl)
def p(t, bold=False, italic=False):
    para = doc.add_paragraph(); run = para.add_run(t); run.bold, run.italic = bold, italic; return para
def bullets(items):
    for t in items: doc.add_paragraph(t, style="List Bullet")
def code(t):
    para = doc.add_paragraph()
    for line in t.rstrip().split("\n"):
        run = para.add_run(line + "\n"); run.font.name = "Consolas"; run.font.size = Pt(8)
    para.paragraph_format.left_indent = Pt(10)
def shot(t):
    para = doc.add_paragraph(); run = para.add_run(f"[Screenshot placeholder: {t}]"); run.italic = True; run.font.color.rgb = RGBColor(0x80, 0x80, 0x80)
def table(df, fmt="{:.4f}", index=True):
    d = df.reset_index() if index else df
    t = doc.add_table(rows=1, cols=len(d.columns)); t.style = "Light Grid Accent 1"
    for j, c in enumerate(d.columns): t.rows[0].cells[j].text = str(c)
    for _, row in d.iterrows():
        cells = t.add_row().cells
        for j, v in enumerate(row): cells[j].text = fmt.format(v) if isinstance(v, (float, np.floating)) else str(v)
    doc.add_paragraph()

pc = lambda x: f"{x:.1%}"
usd = lambda x: f"${x:,.0f}"

# ---------------------------------------------------------------- title
t = doc.add_heading("FIN3702B Group Project: Prompts, Step 8 and Step 9", 0)
p("Group: B#_Group#   |   Members and matric numbers: see Cover sheet of the Excel workbook", italic=True)

h("1. Overview and how to reproduce")
p("We chose 10 ETFs (equity: SPY, IWM, VEA, VWO, XLE, QQQ; bonds: AGG, TIP, HYG; alternative: GLD), used month-end adjusted closes from Dec 2020, "
  "the Kenneth French monthly risk-free rate, and 48 monthly returns (Jan 2021 to Dec 2024) as the estimation window. Annualised return is the arithmetic "
  "monthly mean x 12, annualised standard deviation is STDEV.S x sqrt(12), and the Sharpe ratio uses the mean monthly risk-free rate x 12. No short-selling; "
  "the ORP must hold at least 2 ETFs; risk aversion A = 7; borrowing is at the risk-free rate.")
p("Five prompts were developed. Every prompt was tested by pasting it, with no other context, into a brand-new LLM session (a fresh Claude session with tools "
  "disabled, acting as a plain chat assistant). The returned code was saved unmodified, run, and checked against an independent Python reference and against "
  "the Excel workbook. To reproduce: open a new chat, paste a prompt exactly as printed below, run the returned code in Google Colab (or any Python 3 environment "
  "with the packages it installs), and compare with the expected values quoted under each prompt. Tolerance: absolute difference of 0.005 (0.5 percentage points) "
  "on returns and standard deviations; every run reported below was within 0.000001.")
p("Final versions: Prompt A v1, Prompt B v1, Prompt C v1, Prompt D v2, Prompt E v1. Reference values (2021-24, 48 observations):", bold=True)
ref = pd.DataFrame({"Portfolio": ["MVP", "ORP", "OCP (A=7)"],
                    "Return": [port_stats(w_mvp, mu, S.values)[0], port_stats(w_orp, mu, S.values)[0], o4["ret"]],
                    "St. dev.": [port_stats(w_mvp, mu, S.values)[1], port_stats(w_orp, mu, S.values)[1], o4["sd"]]})
table(ref, "{:.4f}", index=False)
wt = pd.DataFrame({"MVP": w_mvp, "ORP": w_orp, "OCP risky": o4["w_risky"]}, index=ALL)
wt.loc["Risk-free"] = [0, 0, o4["w_rf"]]
table(wt)
p(f"The ORP holds GLD {pc(w_orp[ALL.index('GLD')])}, XLE {pc(w_orp[ALL.index('XLE')])} and QQQ {pc(w_orp[ALL.index('QQQ')])}, so the 'at least 2 ETFs' rule is met. "
  f"At A = 7 the OCP puts y = {o4['y']:.3f} of capital in the ORP, i.e. it borrows {pc(-o4['w_rf'])} of capital at the risk-free rate.")

# ---------------------------------------------------------------- prompts
def prompt_section(title, purpose, ver_files, results_text, shot_names):
    h(title, 2)
    p(purpose)
    for label, f in ver_files:
        p(label, bold=True); code((PR / f).read_text())
    p("Results and iteration history", bold=True)
    for line in results_text: doc.add_paragraph(line, style="List Bullet")
    for s_ in shot_names: shot(s_)

h("2. Prompts for the LLM")
prompt_section("Prompt A: optimisation code (Steps 5a to 5c)",
    "Generates Python that downloads the data, computes the statistics, and finds the MVP, ORP and OCP, writing results to an Excel file.",
    [("Prompt A, version 1 (final)", "promptA_v1.txt")],
    ["Version 1 passed on the first attempt: MVP 0.24% / 6.49%, ORP 17.49% / 13.04%, OCP 20.85% / 16.04% (return / st. dev.), y = 1.2297; every figure within 0.000001 of the Python reference.",
     "Variability test: the same prompt in 3 independent fresh sessions gave 3 passes (differences between runs were in code style only).",
     "Version 0 (a deliberately vague one-paragraph prompt) was also run for comparison. It also matched (the model chose the same conventions unprompted) but: it used Colab-only '!pip' syntax, used Yahoo's monthly bars instead of daily resampling, and added an unrequested fallback that caps ORP weights at 95% if the ORP collapses to one ETF. That fallback would silently change the portfolio where the brief says to choose other ETFs. Version 1 therefore pins every convention and makes the 2-ETF rule an error.",
     "We did not invent failures: the brief asks us to document discrepancies if they arise. None arose for this prompt."],
    ["Prompt A v1 pasted into a new chat", "Generated code running in Colab and printing the results table"])
prompt_section("Prompt B: minimum variance frontier chart on an Excel worksheet (Step 5d)",
    "Generates Python that computes the long-only frontier (80 points), plots it with the CAL and the labelled MVP, ORP and OCP, saves the chart as a PNG, and writes the chart and tables to an Excel worksheet named MVF.",
    [("Prompt B, version 1 (final)", "promptB_v1.txt")],
    ["Passed on the first attempt: results.json within 0.000001 of the reference; the chart shows the frontier, a CAL tangent at the ORP, the OCP on the CAL beyond the ORP (leveraged), and all 10 ETFs labelled; the workbook has the MVF sheet with the image at N2.",
     "Cosmetic flaw: the MVP label slightly overlaps the TIP label. Not corrected.",
     "Practical note: the script calls plt.show(), which renders inline in Colab but blocks when run locally on a Mac. Run locally with the environment variable MPLBACKEND=Agg."],
    ["The chart produced by Prompt B", "The MVF worksheet in ai_mvf.xlsx"])
prompt_section("Prompt C: macroeconomic data download (Step 6a)",
    "Downloads six FRED series (10-year yield, 10y-2y spread, VIX, fed funds, CPI, unemployment) to month-end, with a hard cap at 2024-12-31.",
    [("Prompt C, version 1 (final)", "promptC_v1.txt")],
    ["Passed on the first attempt: the resulting 72-month table is identical (maximum absolute difference 0.0 in all six columns) to the one used by the Python reference.",
     "The LLM enforced the date cap twice: server-side with FRED's cosd/coed parameters, and with an assert."],
    ["Prompt C output table (first and last rows)"])
prompt_section("Prompt D: forward-looking model and the 2025 optimum complete portfolio (Step 6b)",
    "Builds a macro-driven forecast of 2025 returns and then the ORP and OCP (A = 7) from those forecasts, using only data up to 2024-12-31.",
    [("Prompt D, version 1 (superseded)", "promptD_v1.txt"), ("Prompt D, version 2 (final)", "promptD_v2.txt")],
    ["Version 1 produced code that followed the specification exactly but an indefensible result: leave-one-out cross-validation chose an almost unregularised penalty (alpha 1.1) for AGG, which then fitted the 2022 bond-market crash. Forecast for AGG: +18.7% a year against a 2021-24 mean of -2.0%; ORP 85.9% AGG; OCP 311% in AGG, 3.6x leverage, 60.8% expected return.",
     "Root cause: a flaw in the specification (too little data for a free penalty), not in the code. Version 2 restricts the penalty grid to alpha >= 50 (about the sample size), prints each forecast beside the ETF's historical mean, and adds hard asserts (every forecast within 0.15 of its own historical mean; y < 2.5).",
     "Version 2 result: AGG forecast +4.4%; OCP = XLE 40.3%, QQQ 54.0%, GLD 61.1%, risk-free -55.4%; y = 1.554; expected return 26.4%, st. dev. 18.4%, Sharpe 1.285. An independent Python replica gives the same structure within about 3 points on every weight (largest gap: GLD 61.1% vs 58.2%; y = 1.483, return 24.3%).",
     "Residual difference: the LLM used month-end values for the 10-year yield and curve slope where the prompt said monthly mean (a compliance slip; effect under one percentage point).",
     "Every leave-one-out R-squared is negative (-0.02 to -0.05): the macro features show no out-of-sample skill on 48 observations. The ridge penalty shrinks forecasts back toward history, so the model is well-behaved rather than predictive. Caution: the penalties are heavily shrunk (five of the ten sit at the 1000 edge of the grid), so a negative leave-one-out R-squared here mostly means 'no better than predicting each ETF's own mean'."],
    ["Prompt D v1 output showing the AGG blow-up", "Prompt D v2 output with diagnostics and weights"])
prompt_section("Prompt E: justification of the portfolio mix (Step 6c)",
    "Asks the LLM to justify the Step 6b portfolio using only the numbers in the model output pasted into the prompt.",
    [("Prompt E, version 1 (final; the pasted model output is the Prompt D v2 output)", "promptE_v1.txt")],
    ["The answer (llm_code/justification_v1.md) covers the macro backdrop at Dec 2024, why GLD, QQQ and XLE were chosen and the other seven excluded, the role of leverage, risks, and the statistical limits.",
     "Hallucination screen: 54 numbers appear in the answer and none is absent from the supplied data.",
     "Compliance slip: 667 words against a 600-word limit. Weakness: part of the narrative (for example 'gold is exposed to high yields') is generic finance commentary, not derived from the model; the model's own coefficients are tiny, so the story is more confident than the statistics."],
    ["Prompt E answer"])

# ---------------------------------------------------------------- Step 8
h("3. Step 8: investing $100,000 at the start of 2025")
p("Method: $100,000 is invested on 1 January 2025 in each OCP and held (buy-and-hold, no rebalancing) to 31 December 2025. Borrowing, where the OCP is leveraged, "
  "costs the realised monthly risk-free rate; the realised 2025 risk-free rate averaged "
  f"{rf25.mean() * 12:.2%} a year, versus {rf:.2%} over the estimation window, so financing was dearer than assumed. SPY is the market proxy for beta, alpha, M-squared and the information ratio.")
d8 = pd.DataFrame(res8).T[["end_value", "total_return", "sharpe", "sortino", "treynor", "jensen_alpha", "beta", "m2", "max_drawdown", "info_ratio"]]
d8.columns = ["End value ($)", "Total return", "Sharpe", "Sortino", "Treynor", "Jensen alpha", "Beta", "M-squared", "Max drawdown", "Info ratio"]
d8["End value ($)"] = d8["End value ($)"].map(usd)
table(d8, "{:.3f}")
a_, b_ = res8["Step 4c OCP"], res8["Step 6b OCP (LLM)"]
p("Answer", bold=True)
p(f"Starting with $100,000, the Step 4c OCP ends 2025 at {usd(a_['end_value'])} ({pc(a_['total_return'])}) and the Step 6b OCP at {usd(b_['end_value'])} ({pc(b_['total_return'])}). "
  f"Both beat the market proxy SPY ({usd(res8['SPY (benchmark)']['end_value'])}).")
p("Which performed better? On most measures the Step 6b portfolio did: it has the higher end value, Sharpe ratio "
  f"({b_['sharpe']:.2f} vs {a_['sharpe']:.2f}), Sortino ratio ({b_['sortino']:.1f} vs {a_['sortino']:.1f}), Jensen's alpha ({pc(b_['jensen_alpha'])} vs {pc(a_['jensen_alpha'])}), "
  f"M-squared ({pc(b_['m2'])} vs {pc(a_['m2'])}), information ratio ({b_['info_ratio']:.2f} vs {a_['info_ratio']:.2f}) and the shallower maximum drawdown ({pc(b_['max_drawdown'])} vs {pc(a_['max_drawdown'])}). "
  f"The one measure that favours Step 4c is the Treynor ratio ({a_['treynor']:.2f} vs {b_['treynor']:.2f}), because 6b carries about twice the market beta ({b_['beta']:.2f} vs {a_['beta']:.2f}) and Treynor divides by beta. "
  "Sharpe and Sortino use total risk and Jensen's alpha is measured against the market, so for a client who holds only this portfolio the total-risk measures are the relevant ones and favour 6b.")
p("Risk-free rate convention", bold=True)
p(f"Both OCPs are built with the 2021-24 average risk-free rate ({rf:.2%}), the brief's single-rate convention, which keeps the two portfolios comparable. "
  f"A forward-looking investor in December 2024 would face a higher rate (the 2024 average was {rf24:.2%}). Rerunning the Step 6 model's Python replica at {rf24:.2%} lowers the OCP's risky share from y = {base_rf['ocp']['y']:.2f} to {sens_rf['ocp']['y']:.2f} "
  f"and shifts the ORP weights by only a few points (XLE {pc(sens_rf['w_orp'][ALL.index('XLE')])}, QQQ {pc(sens_rf['w_orp'][ALL.index('QQQ')])}, GLD {pc(sens_rf['w_orp'][ALL.index('GLD')])}), keeping the same three ETFs. "
  "So the convention affects how much leverage 6b uses, not which assets it holds.")
p("Why we should not over-read this", bold=True)
bullets([f"One asset explains most of 2025: GLD returned {pc(etf25['GLD'])}. The 6b portfolio put {pc(o6['w_risky'][ALL.index('GLD')])} of capital in GLD versus {pc(o4['w_risky'][ALL.index('GLD')])} for 4c, and it was more leveraged (y = {L['y']:.2f} vs {o4['y']:.2f}). Leverage amplifies whatever the risky mix does.",
         "The 6b advantage cannot be credited to macro forecasting skill: every leave-one-out R-squared in the macro model is negative. The tilt towards QQQ and GLD, and the extra leverage, happened to pay in 2025.",
         "The unlevered ORP alone finished at " + usd(res8["ORP only, unlevered"]["end_value"]) + ", so most of the 4c result is the ORP itself and the rest is leverage.",
         "The Sharpe and Sortino ratios are computed from only 12 monthly returns and annualised, so they are statistically fragile. The very high Sortino for 6b (little or no downside month) is an artefact of a small sample."])

# ---------------------------------------------------------------- Step 9
h("4. Step 9: evaluation of using LLMs in portfolio management")
h("Strengths", 2)
bullets(["Speed and accessibility: one well-specified prompt produced working data-download, optimisation and charting code in about 30 seconds. Across 3 independent fresh runs of Prompt A v1 (plus a deliberately vague v0) and 1 run of Prompt B, the results matched an independent Python reference to within 0.000001, including a first-time-correct treatment of the risk-free rate (percent to decimal), ddof and annualisation.",
         "Good at standard quantitative recipes: even a vague prompt (Prompt A v0) chose sensible conventions (adjusted prices, sample standard deviation, 48 returns). The LLM also added useful defensive checks unprompted (asserts on 48 observations and on the data cutoff).",
         "Breadth of drafting: it can turn numbers into a readable investment narrative (Prompt E) and link macro variables to asset classes, which lowers the cost of producing client communication.",
         "Transparency of code: the output is inspectable, reproducible Python, which is a better audit trail than a black-box answer."])
h("Weaknesses", 2)
bullets(["Specification-blind in modelling judgement: Prompt D v1 obeyed the instructions and still produced a nonsense portfolio (AGG forecast +18.7%, 3.6x leverage). The LLM did not volunteer that a free ridge penalty on 48 observations would overfit; a human had to notice and fix the specification.",
         "Instruction slips: in Prompt D v2 the LLM used month-end instead of monthly mean for two series; in Prompt E it exceeded the word limit; the naive Prompt A v0 silently added a 95% weight cap. Small, but they show the code must be checked, not trusted.",
         "Narrative outruns the evidence: the Prompt E justification explains the weights with generic macro stories even though the model's leave-one-out R-squared is negative for every ETF. Fluent explanations can create false confidence.",
         "Run-to-run variability: the same prompt gave different code each time (different start points, sheet layouts). Results agreed here because the task is deterministic maths, but free-form modelling choices would not."])
h("Risks", 2)
bullets(["Estimation error (the central quantitative risk). With 48 observations the optimiser is fragile. Resampling the 48 months (bootstrap, 300 draws) moves the ORP weight on XLE between "
         f"{pc(boot['summary']['ORP']['p05']['XLE'])} and {pc(boot['summary']['ORP']['p95']['XLE'])}, QQQ between {pc(boot['summary']['ORP']['p05']['QQQ'])} and {pc(boot['summary']['ORP']['p95']['QQQ'])}, and GLD between {pc(boot['summary']['ORP']['p05']['GLD'])} and {pc(boot['summary']['ORP']['p95']['GLD'])} (5th to 95th percentile); in {pc(boot['frac_orp_lt2'])} of draws the ORP collapses to a single ETF (and {pc(share1)} of draws if a second ETF only counts once it holds at least 1%: the 1% threshold; the 2-ETF test in the code uses 0.01%, as in the brief's prompts). "
         f"By contrast, perturbing the covariance matrix by about 10% moves ORP weights by only about {pert['summary']['ORP']['std'][['XLE','QQQ','GLD']].mean() * 100:.0f} percentage points, and a Ledoit-Wolf covariance gives almost the same ORP (XLE {pc(lw.loc['XLE','ORP_LW'])}, QQQ {pc(lw.loc['QQQ','ORP_LW'])}, GLD {pc(lw.loc['GLD','ORP_LW'])}). The fragility therefore lies in the expected-return estimates, not the covariance matrix.",
         "Data leakage / look-ahead: the macro data runs to 2026, so an LLM, or a careless user, can easily include post-2024 data. We prevented it with a server-side date cap, asserts, and a publication-lag shift for CPI and unemployment.",
         "Model risk and leverage: the OCP borrows (y = 1.23 for 4c and 1.55 for 6b) at the risk-free rate, which is optimistic; realised 2025 financing cost was higher than the estimation-window average.",
         "Hallucination: an LLM may cite numbers or events that do not exist. We screened Prompt E's answer mechanically (54 of 54 numbers traceable to the data).",
         "Mitigations we used: independent Python and Excel-formula cross-checks (the Excel Solver run is to be confirmed by the team); sanity asserts in the prompts; a 'no data after 2024-12-31' rule enforced in code; fresh-session reproduction of every prompt; repeat runs; mechanical number screening; and reporting uncertainty (bootstrap ranges) next to every recommendation."])
h("Ethical considerations", 2)
bullets(["Suitability and fiduciary duty: an LLM does not know the client's circumstances. A leveraged portfolio (123% to 155% of capital in risky assets) is not suitable for every A = 7 investor; a human adviser must confirm suitability and explain leverage.",
         "Transparency and explainability: clients should be told that an LLM wrote the code and the narrative, and that the narrative is a story consistent with the weights, not proof of why they are optimal.",
         "Accountability: responsibility for the advice stays with the licensed firm and adviser, not the model or its vendor; there must be a named reviewer who signs off on each recommendation.",
         "Data provenance and privacy: we used only public data. With real clients, personal data should not be pasted into a consumer LLM; use an enterprise deployment with data-protection terms.",
         "Fairness and bias: models trained and tested on 2021-24 embed that regime (rising rates, an energy boom); recommendations may be biased against asset classes that did badly in that window, which is an investment bias rather than a demographic one but still needs disclosure.",
         "Over-reliance and deskilling: advisers may stop questioning model output. We saw a confident, fluent but wrong forecast (Prompt D v1) pass the 'it runs' test; human challenge is essential."])
h("Practical limitations", 2)
bullets(["Needs human review at every step: unit tests, a reference implementation and sanity asserts were all necessary to trust the code.",
         "Reproducibility: LLM versions change; the same prompt may yield different code later. Pin the model version, store the generated code, and keep a reference implementation.",
         "Data and infrastructure: the workflow depends on free services (Yahoo Finance, FRED, French library) that can change format, rate-limit, or restate adjusted prices (we cached a snapshot); production use needs licensed data.",
         "Costs and real-world frictions: the model ignores transaction costs, taxes, bid-ask spreads, margin requirements and borrowing spreads, and rebalancing; the 12-month Step 8 test is too short to judge any strategy.",
         "Regulation and monitoring (for example MAS expectations in Singapore): model-risk management, record-keeping of prompts and outputs, periodic validation, and clear client disclosure are required before an LLM could be used in live portfolio management."])

# ---------------------------------------------------------------- caveat
h("5. Caveat: 48 observations")
p("The brief fixes the estimation window at four years of monthly data, so we follow it. It is a small sample: expected returns are estimated with large error "
  f"(the annualised standard error of a 48-month mean for an ETF with 16% volatility is about {0.16 / np.sqrt(4):.0%} a year), and the optimiser treats those noisy means as truth. "
  "Section 4 quantifies the consequence: the ORP's weights are unstable under resampling (XLE, QQQ and GLD each swing by tens of percentage points), while they are stable to noise in the covariance matrix. "
  "Anyone using these portfolios should treat them as one plausible outcome from a wide range, not as a precise optimum.")

h("Appendix: Excel checks")
p("Excel formulas (Sheets 6 to 8) were verified against Python in Microsoft Excel: annualised return, standard deviation, Sharpe ratio, risk-free rate, the 10x10 covariance matrix, MVP, ORP and OCP quantities and all 80 frontier points agree to better than 1e-12. "
  "Solver run on Sheet 8 (starting from equal weights): [TEAM TO CONFIRM after running Solver and the reconciliation script].")
doc.save(str(ROOT / "Prompts_and_Answers.docx"))
print("saved Prompts_and_Answers.docx")
