# Prompts log (working document)

Method: each prompt is given, verbatim and with no other context, to a fresh LLM session (a fresh Claude subagent with
tools disabled, acting as a plain chat assistant). The returned code is saved unmodified, run, and checked against the
Python reference (`tests/check_llm_results.py`, tolerance 0.005 absolute on return and st. dev.).

Reference values (Python, 2021-24, 48 obs): ORP = GLD 39.2%, XLE 37.9%, QQQ 22.9%; ORP return 17.49%, sd 13.04%;
MVP return 0.24%, sd 6.49%; OCP (A=7) y = 1.2297, return 20.85%, sd 16.04%.

## Prompt A: optimisation code (Steps 5a-5c)

### v1
Text: `prompts/promptA_v1.txt`.

Result (fresh Claude subagent, tools disabled): **PASS on the first attempt.** Every figure matched the Python reference to <= 1e-6
(MVP 0.24% / 6.49%, ORP 17.49% / 13.04%, OCP 20.85% / 16.04%, y = 1.2297).
Code saved verbatim in `llm_code/optimiser_v1.py`; output in `llm_code/optimiser_v1/`.

### Variability test (same v1 prompt, 3 independent fresh sessions)
| Run | File | Check | Max abs diff vs Python |
|---|---|---|---|
| 1 | `optimiser_v1.py` | PASS | < 1e-6 |
| 2 | `optimiser_v1_run2.py` | PASS | 1e-6 (MVP sd 0.064897 vs 0.064898) |
| 3 | `optimiser_v1_run3.py` | PASS | 1e-6 (OCP ret 0.208518 vs 0.208517) |

Differences between runs are in code style only (start-point schemes, how the Excel sheet is laid out), not in results.

### v0 (deliberately naive prompt, run for comparison)
Text: "Write Python code (for Google Colab) that downloads monthly price data ... Get the risk-free rate from the Kenneth French data
library ... Calculate each ETF's annualised average monthly return, annualised standard deviation and Sharpe ratio. Then find the minimum
variance portfolio, the optimal risky portfolio (no short selling, at least 2 ETFs) and the optimal complete portfolio for a risk aversion
of 7 ... save results.json with keys mvp/orp/ocp, each containing ret and sd."

Result: **also PASS** (diff <= 1e-6). The model chose the same conventions unprompted: adjusted prices, ddof = 1, RF percent to decimal,
48 returns. Observations: (1) it used Yahoo's monthly bars (`interval="1mo"`) instead of resampling daily data, with identical results here;
(2) it began with a Colab-only `!pip install` line, which does not run as a plain .py file (commented out in the runnable copy; the saved
file is verbatim); (3) it added an unrequested fallback (cap ORP weights at 95% if the ORP collapses to one ETF), which would silently
change the portfolio in a case where the brief says to choose other ETFs.

Conclusion: for this task a loose prompt happens to work, but v1 is kept as the reference prompt because it pins down every convention
(so a different LLM, or a later model version, cannot drift) and it makes the ORP >= 2 ETFs rule an error, as the brief requires.
We did not invent failures to fill the discrepancy log: the brief asks to document discrepancies *if* they arise.

## Prompt B: frontier chart written to an Excel worksheet (Step 5d)

### v1
Text: `prompts/promptB_v1.txt` (self-contained: repeats the data and statistics spec, adds the 80-point long-only frontier, the labelled
chart with CAL, and the Excel/PNG output requirements).

Result (fresh Claude subagent, tools disabled): **PASS on the first attempt.**
- `results.json` matches Python to <= 1e-6 (MVP 0.24% / 6.49%, ORP 17.49% / 13.04%, OCP 20.85% / 16.04%).
- Chart (`llm_code/mvf_v1/mvf_ai.png`) checked by eye: frontier is the expected sideways curve with the MVP at its left tip; the CAL is
  tangent to the frontier at the ORP; the OCP lies on the CAL beyond the ORP (leveraged, y = 1.23); all 10 ETFs, MVP, ORP and OCP are labelled.
- `ai_mvf.xlsx` has the single worksheet "MVF" with the 80-point table, the MVP/ORP/OCP table and the chart image at N2 (1 image, 93 rows).
- Cosmetic flaw: the MVP label slightly overlaps the TIP ticker label. Not fixed (no effect on numbers).

Practical note: the script calls `plt.show()`. In Colab this renders inline; run locally on macOS with a GUI backend it blocks until the window is
closed (it hung our first local run). Run with `MPLBACKEND=Agg` locally. Sheet 3 of the workbook embeds this PNG.
