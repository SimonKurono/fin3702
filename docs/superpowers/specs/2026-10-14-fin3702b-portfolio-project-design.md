# FIN3702B Group Project: Technical Pipeline Design

Date: 2026-10-14. Deadline: Fri 30 Oct 2026, 5pm. Owner of this spec: the technical workstream (Excel, Python, prompts doc). The rest of the group handles the presentation.

## 1. Goal

Deliver the Excel workbook and the Word/PDF prompts document for the FIN3702B group project, and make them as strong as the rubric allows. Python is the source of truth. The Excel workbook uses live formulas, the user runs Solver on it, and the two must agree within the brief's tolerance (±0.5% on returns and standard deviation).

Any LLM is permitted (the professor allowed any model, given free NUS ChatGPT access). Prompts must still be self-contained, because the professor will paste them into a fresh chat.

## 2. Fixed decisions

| Item | Decision |
|---|---|
| ETFs (10) | Equity: SPY, IWM, VEA, VWO, XLE, QQQ. Bonds: AGG, TIP, HYG. Alternative: GLD. |
| Price basis | Month-end adjusted close (total return). Sheet 4 shows Close and Adj Close. |
| Estimation window | Dec 2020 base price, giving 48 monthly returns (Jan 2021 to Dec 2024). Fixed by the brief. |
| Hold-out | 2025 monthly data is used only in Step 7 and Step 8. |
| Annualised return | Arithmetic monthly mean × 12. |
| Annualised st. dev. | Sample st. dev. (`STDEV.S`) × √12. |
| Risk-free rate | French `RF` column ÷ 100. Annualised as mean monthly RF × 12. |
| Constraints | No shorting. Weights sum to 1. ORP must hold at least 2 ETFs with weight above 0. OCP may borrow at RF. |
| Risk aversion | A = 7. OCP risky weight y* = (E[r_ORP] − rf) / (A σ²_ORP). |
| Step 6 model | Macro regression plus optimiser. |
| Extras | Core, Ledoit-Wolf sensitivity, robust Step 8 metrics. |
| Project location | `~/Developer/FIN3702B_Project` (outside iCloud; the Desktop folder is iCloud-synced and evicted files). Final deliverables are copied to the Desktop project folder. |

Dry run on 2026-10-14 confirmed that Yahoo, French and FRED all supply the required data with no gaps. A quick long-only max-Sharpe check gave GLD 39%, XLE 38%, QQQ 23% (Sharpe about 1.12), which satisfies the 2-ETF rule.

## 3. Repo layout

```
config.py            tickers, windows, A=7, hard cap on macro date (2024-12-31)
data.py              ETF prices (Yahoo), RF (French), macro (FRED), cached CSVs
optimize.py          MVP, ORP, OCP, frontier, CAL
forward_model.py     Step 6: lagged-macro regression, expected returns, A=7 OCP
evaluate.py          Step 8: $100k path, Sharpe, Sortino, max drawdown, alpha, beta
robustness.py        Ledoit-Wolf and covariance perturbation sensitivity
build_workbook.py    writes the .xlsx with live formulas
llm_code/            code produced from the user's prompts, tested here
tests/               Python vs Excel reconciliation
```

## 4. Excel workbook

- Cover sheet: section, group number (`B#_Group#`), names and matric numbers (left for the user to fill in).
- Sheet 1: executive summary with weights, return, st. dev. and Sharpe for MVP, ORP, OCP (4c) and OCP (6b).
- Sheet 2: native Excel scatter chart of the minimum variance frontier, with labelled MVP, ORP and OCP and the CAL.
- Sheet 3: the AI-generated MVF chart (image from the LLM-produced matplotlib code).
- Sheet 4: raw monthly prices for the 10 ETFs.
- Sheet 5: French data and macro data.
- Sheet 6: monthly returns, annualised return, st. dev. and Sharpe, all as formulas. No hardcoded values.
- Sheet 7: covariance matrix (`COVARIANCE.S`).
- Sheet 8: Solver set-up for MVP, ORP, OCP, all formula-driven. The user runs Solver three times. Pre-loading the Solver settings into the file is best-effort.

## 5. LLM section (Steps 5, 6, 9)

Prompts document contains, in order: Prompt v1, the discrepancy log (source of each mismatch against Excel), refined prompts, the MVF-chart prompt, the macro-download prompt, the forward-looking-model prompt, and the justification prompt. Every prompt names the exact tickers, dates, A=7, data URLs and output format. Each is tested in a fresh chat before it goes in the document.

Step 6 model: regress each ETF's monthly returns on one-month-lagged macro variables, using ridge or similar shrinkage because n = 48. Candidate variables are the 10-year yield, the 10y-2y spread, CPI inflation, unemployment, VIX and fed funds. All inputs are hard-capped at 2024-12-31. The fitted model gives expected returns for 2025, which feed the same A=7 optimiser to produce the Step 6b OCP.

## 6. Step 8 and robustness

- Step 8: $100,000 on 1 Jan 2025 into each OCP (4c and 6b), no rebalancing. Report end value, return, Sharpe, Sortino, max drawdown, and alpha and beta against SPY.
- Ledoit-Wolf: compare sample and shrunk covariance, then perturb the matrix over many random draws and report how much the MVP, ORP and OCP weights move.

## 7. Required caveat (goes in the write-up)

Using 48 monthly observations is mandated by the brief, so we follow it. The write-up must state that this is a small sample: expected returns and covariances are estimated with substantial error, and optimiser outputs (especially the ORP) are highly sensitive to that error. The Ledoit-Wolf and perturbation results are the evidence for this point. They feed the Step 9 discussion of risks and practical limitations.

## 8. Risks

- The Step 6 model may not beat the Step 4c OCP in 2025. The brief asks for a comparison and explanation, not a win.
- Solver settings may not pre-load. The sheet is still set up for a manual run.
- The user's Mac Excel must have the Solver add-in enabled.
- Group number, names and matric numbers are needed for the cover sheet.
- iCloud-synced folders can evict files and crash git; keep the build outside them.
