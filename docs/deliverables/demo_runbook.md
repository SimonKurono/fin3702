# Live demo runbook (15-minute client pitch)

## The one-minute story
"Give our LLM one precise prompt and it writes, in about 30 seconds, working code that finds the minimum variance, optimal risky and optimal
complete portfolios. We check it three ways (Excel Solver, an independent Python model, and repeat runs). Here it is, live."

## What to paste and what to expect
1. Open a NEW chat (ChatGPT or Claude, no files attached). Paste **Prompt A v1** from `Prompts_and_Answers.docx` (section 2) or
   `docs/deliverables/prompts/promptA_v1.txt`. Generation takes about 30 to 60 seconds.
2. Copy the code into Google Colab and Run all. About 15 to 30 seconds (Yahoo and French downloads, then the optimisation).
3. Expected output (return / st. dev.), tolerance 0.5 percentage points:

| Portfolio | Return | St. dev. | Weights |
|---|---|---|---|
| MVP | 0.24% | 6.49% | TIP 57.2%, AGG 36.0%, GLD 3.9%, XLE 2.9% |
| ORP | 17.49% | 13.04% | GLD 39.2%, XLE 37.9%, QQQ 22.9% (Sharpe 1.123) |
| OCP, A = 7 | 20.85% | 16.04% | y = 1.2297: ORP x 1.23, risk-free -22.97% (borrowing) |

4. Show Sheet 8 of the workbook: the same three portfolios, and Data > Solver > Solve to show Excel finding them (about 20 seconds).
5. For the forward-looking model, show **Prompt D v2** output (do not run it live; allow 60 seconds): OCP = GLD 61.1%, QQQ 54.0%, XLE 40.3%,
   risk-free -55.4%; y = 1.55. Say the macro features have no proven out-of-sample skill (all leave-one-out R-squared below zero).

## Safety net if something fails (prepare before the session)
- Keep a pre-run notebook or the saved outputs ready: `llm_code/optimiser_v1/` (run.log, results.json, ai_results.xlsx) and `llm_code/mvf_v1/mvf_ai.png`.
- Keep screenshots of a successful run in the deck.

## Failure modes seen in testing, and the fix
| Symptom | Cause | Fix |
|---|---|---|
| Script hangs after printing results (local Mac run) | `plt.show()` waits for a GUI window | Run in Colab, or set `MPLBACKEND=Agg` |
| `SyntaxError` on a line starting with `!pip` | Colab-only syntax run as a plain .py file | Run in Colab, or delete that line |
| Yahoo returns nothing or rate-limits | free API | Retry once; otherwise show the saved run |
| LLM "helpfully" caps ORP weights at 95% (seen with a vague prompt) | prompt did not forbid it | Use Prompt A v1 exactly, which makes the 2-ETF rule an error |
| Different layout of the Excel output each time | LLM style varies | Numbers are what must match, not layout |

## Tips for the sceptical client
Concede the weaknesses first (48 observations, leverage, LLM slips) and show the controls. See `qa_cheatsheet.md`.
