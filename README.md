# FIN3702B Group Project: portfolio optimisation pipeline

Builds an Excel workbook (live formulas, Solver-ready) and Python results for 10 ETFs: minimum variance portfolio (MVP),
optimal risky portfolio (ORP, long-only, at least 2 holdings), optimal complete portfolio (OCP, risk aversion A = 7,
borrowing at the risk-free rate allowed), a macro-driven forward-looking OCP, a $100,000 2025 hold-out test, and
Ledoit-Wolf / bootstrap robustness checks.

Default portfolio: SPY, IWM, VEA, VWO, XLE, QQQ (equity), AGG, TIP, HYG (bonds), GLD (alternative).
Estimation window: 48 monthly returns, Jan 2021 to Dec 2024. 2025 is a hold-out used only in Step 8.

## Start here: main files

**Deliverables**
- [Excel workbook](FIN3702B_Portfolio.xlsx): Cover and S1 to S8 (summary, frontier chart, AI chart, prices, macro, returns, covariance, Solver set-up)
- [Excel workbook for a Solver test](FIN3702B_SolverTest.xlsx): same, starting from equal weights
- [Prompts and answers (Word)](Prompts_and_Answers.docx): all prompts, Step 8 and Step 9 answers, the 48-observation caveat

**Results and charts**
- [Frontier chart made by the LLM code (PNG)](llm_code/mvf_v1/mvf_ai.png) and [its Excel output](llm_code/mvf_v1/ai_mvf.xlsx)
- [LLM optimiser output (Excel)](llm_code/optimiser_v1/ai_results.xlsx) and [forward-model output (Excel)](llm_code/forward_model_llm_v2/forward_results.xlsx)
- Saved Python results: [Step 4](docs/results_step4.txt), [Step 6](docs/results_step6.txt), [Step 8](docs/results_step8.txt), [robustness](docs/results_robustness.txt)
- [Excel vs Python reconciliation](docs/reconciliation.md)

**Prompts**
- [Prompt files A to E](docs/deliverables/prompts/) and the [prompt test log](docs/deliverables/prompts_log.md)
- [Demo runbook](docs/deliverables/demo_runbook.md) and [Q&A cheat sheet](docs/deliverables/qa_cheatsheet.md)

**Main code**
- [config.py](config.py) (tickers, dates) | [data.py](data.py) | [optimize.py](optimize.py) (MVP, ORP, OCP) | [forward_model.py](forward_model.py) (Step 6)
- [evaluate.py](evaluate.py) (Step 8) | [robustness.py](robustness.py) | [build_workbook.py](build_workbook.py) | [run_analysis.py](run_analysis.py) | [make_report.py](make_report.py) | [package.py](package.py)
- [Code the LLM wrote, unmodified](llm_code/) and [tests](tests/)

## 1. Set up (once)

Needs Python 3.10+ and internet access (Yahoo Finance, Ken French's library, FRED). Excel with the Solver add-in is needed only for the Solver step.

```bash
git clone <this repo> && cd FIN3702B_Project
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -q                          # optional: 38 tests, about 1 minute
```

## 2. Run it

| I want to... | Command |
|---|---|
| See all results in the terminal (MVP, ORP, OCP, Step 6b, Step 8, Ledoit-Wolf) | `python run_analysis.py` |
| Build the Excel workbook | `python build_workbook.py` (writes `FIN3702B_Portfolio.xlsx`) |
| Build a workbook that starts Solver from equal weights (a real Solver test) | `python build_workbook.py FIN3702B_SolverTest.xlsx --equal-start` |
| Check Excel against Python after running Solver | `python tests/reconcile.py FIN3702B_SolverTest.xlsx` |
| Build the prompts document (default 10 ETFs only) | `python make_report.py` |
| Zip the deliverables | `python package.py B1_Group1` (use your group token) |

Price, Fama-French and FRED data are downloaded on first use and cached in `data/`. Delete a CSV there to re-download it.

## 3. Use your own 10 instruments

Set two environment variables. No code changes needed.

```bash
export FIN_TICKERS="SPY,EFA,EEM,VNQ,XLK,XLU,TLT,LQD,SHY,SLV"   # exactly 10 distinct Yahoo tickers
export FIN_BENCHMARK="SPY"                                      # one of the 10; used for beta, alpha, information ratio
python run_analysis.py
python build_workbook.py MyPortfolio.xlsx
```

Windows PowerShell: `$env:FIN_TICKERS="..."`. Unset the variables to return to the default ETFs.

What to know:
- It must be exactly 10 tickers, because the workbook layout is 10 columns wide (B to K). All of them need prices from Dec 2020 to Dec 2025.
- Prices for each ticker set are cached separately (`data/custom_<tickers>/`), so switching portfolios never mixes data.
- The ORP must hold at least 2 instruments. If one asset dominates, the optimiser raises `ORPConcentrationError`; choose a different mix.
- Sheet 3 (the AI chart), the Step 6b column from the saved LLM run, and `make_report.py` belong to the default ETFs. With custom tickers, Step 6b uses the Python replica of the macro model, Sheet 3 holds a note, and `make_report.py` refuses to run. To get the AI chart and AI Step 6b for your tickers, edit the tickers in the prompts (section 5) and run them in an LLM.
- Dates, risk aversion (A = 7) and the macro series are in `config.py`.

## 4. Run Solver in Excel

1. Open the workbook, go to `S8_Solver`, and follow the instructions in rows 33 to 37 (MVP, ORP, OCP).
2. Save the file from Excel. The cached values are needed by `package.py`.
3. Run `python tests/reconcile.py <file>.xlsx`; Excel and Python should agree to about 1e-6.

Tab guide: Cover, S1 summary, S2 native frontier chart, S3 AI chart, S4 prices, S5 French and macro data, S6 returns and statistics (formulas), S7 covariance (`COVARIANCE.S`), S8 Solver set-up.

## 5. Where everything is

```
config.py            tickers, dates, A, FIN_TICKERS / FIN_BENCHMARK handling
data.py              downloads and caches prices (Yahoo), RF (French), macro (FRED, capped at 2024-12-31)
optimize.py          returns, covariance, MVP, ORP, OCP, frontier
forward_model.py     Step 6: lagged macro features, ridge regression, Ledoit-Wolf covariance, 2025 OCP
evaluate.py          Step 8: $100k buy-and-hold path, Sharpe, Sortino, Treynor, alpha, M-squared, drawdown
robustness.py        Ledoit-Wolf, covariance perturbation and bootstrap sensitivity
build_workbook.py    writes the .xlsx
run_analysis.py      prints the Python results
make_report.py       builds Prompts_and_Answers.docx (default ETFs)
package.py           zips the deliverables
llm_code/            code the LLM wrote from our prompts, saved unmodified, with its outputs
tests/               unit tests, Excel-vs-Python reconciliation, LLM-output checks
docs/deliverables/   prompts (prompts/), prompt test log, demo runbook, Q&A cheat sheet
docs/results_*.txt   saved Python results
```

The five LLM prompts are in `docs/deliverables/prompts/`: A (optimiser), B (frontier chart to Excel), C (macro download), D v2 (forward model), E (justification). They name the tickers explicitly, so to use them with your own set, replace the ticker list and, for Prompt A and B, check the expected results against `python run_analysis.py`. `docs/deliverables/prompts_log.md` records how each was tested.

## 6. Method in one paragraph

Annualised return is the monthly mean times 12; standard deviation is the sample standard deviation times the square root of 12; the covariance matrix is annualised the same way; the risk-free rate is Ken French's monthly RF averaged over the window. Weights come from SLSQP with multiple starts. The OCP risky share is y = (E[r_ORP] - rf) / (A x variance_ORP), and y above 1 means borrowing at the risk-free rate. Step 6 fits a ridge regression per ETF on six macro variables lagged one month (CPI and unemployment lagged two, for publication delay), with penalty at least 50, then forecasts 2025 from the December 2024 state. No 2025 data is used to fit anything.

## 7. Limits

- 48 monthly observations is a small sample. The ORP is sensitive to the expected-return estimates (bootstrap) far more than to the covariance matrix (perturbation and Ledoit-Wolf). Treat the weights as one estimate, not a precise answer.
- The macro model has no out-of-sample skill (every leave-one-out R-squared is negative); do not read its 2025 result as forecasting skill.
- The Solver settings stored in the workbook are best-effort; the manual instructions on `S8_Solver` always work.
- Yahoo and FRED values can be restated; the cached CSVs in `data/` keep the numbers reproducible.
