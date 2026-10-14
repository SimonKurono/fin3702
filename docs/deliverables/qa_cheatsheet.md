# Q&A cheat sheet (sceptical client)

**Why only 48 months of data?** The brief fixes it, and we say so. It is a small sample: the standard error of a 48-month mean for a 16%-vol ETF is about 8% a year.
We measured the effect: resampling the 48 months moves the ORP's XLE weight between 3.9% and 84.4%, QQQ 0% to 70.7%, GLD 0% to 69.8% (5th to 95th percentile),
and 5% of resamples collapse the ORP to one ETF. So we present the portfolio as one plausible outcome, not a precise optimum.

**How stable are the weights?** Very stable to noise in the covariance matrix (10% perturbation moves ORP weights about 3 points; Ledoit-Wolf gives XLE 39%, QQQ 24%, GLD 36%
against 38%, 23%, 39%). Not stable to noise in expected returns. The fragility is in the means.

**Why not just buy the S&P 500?** In sample SPY's Sharpe was 0.69 against 1.12 for the ORP. In 2025, $100,000 became $117,719 in SPY, $139,238 in our 4c OCP and $150,932 in the 6b OCP.
Be honest: 2025 was a gold year (GLD +63.7%) and both OCPs are leveraged; one year proves little.

**Did the macro model beat the sample model?** On most 2025 measures yes (Sharpe 3.82 vs 3.30, alpha 32.5% vs 27.1%), but on Treynor no (0.86 vs 1.41). We do not claim skill:
every leave-one-out R-squared was negative. The tilt to QQQ and GLD, plus more leverage (1.55 vs 1.23), happened to pay.

**Why is XLE so large?** Energy had the best 2021-24 Sharpe (0.905) because of the 2021-22 energy boom. A backward-looking optimiser chases it. That is a reason for caution, and why we show the sensitivity.

**You borrow. What if borrowing costs more?** The model assumes borrowing at the risk-free rate. In 2025 the realised risk-free rate averaged 4.17% against 2.84% assumed, and real brokers charge a spread above that.
Without leverage the ORP alone finished 2025 at $132,704. Both OCPs also use the 2021-24 average risk-free rate (2.84%), the brief's convention; at the 2024 average (5.13%) the 6b risky share would fall from 1.48 to 1.21 with the same three ETFs.

**What if the LLM hallucinates or writes wrong code?** We never trust it unchecked: (1) the maths is reproduced independently in Python and in Excel formulas (agreement better than 1e-12) and in the LLM's code (1e-6); the Excel Solver run is to be completed by the team before presenting; (2) the prompts contain hard rules and assert checks;
(3) every prompt was reproduced in a fresh session and repeated; (4) the narrative was screened mechanically (54 of 54 numbers traceable). We also show the failure we caught: Prompt D v1 forecast AGG at +18.7% a year until we fixed the specification.

**Who is accountable?** The firm and a named adviser, never the model. A human signs off every recommendation and the prompts, code and outputs are kept as the audit trail.

**What happens in a regime change?** The model is estimated on 2021-24 (rising rates, energy boom, bond losses). It has no mechanism to anticipate a regime shift, and the macro features showed no out-of-sample skill. We monitor, cap leverage and re-estimate.

**Client data and privacy?** This project used public data only. For real clients we would use an enterprise LLM deployment under data-protection terms and never paste personal data into a consumer chatbot.

**Cost and practicality?** Free data (Yahoo, FRED, French) and a free LLM, minutes of runtime. A production version would need licensed data, transaction costs, taxes, margin rules and MAS-style model-risk governance.

**How do I know the 'optimal' portfolio is right?** Excel formulas, Python and the LLM's code all agree on the same weights and statistics (Solver run to be confirmed by the team). 'Right' here means the mean-variance optimum of the sample, which is only as good as the sample.
