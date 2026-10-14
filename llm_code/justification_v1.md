## 1. Macro backdrop at December 2024

The 10-year yield (y10) is 4.5800 and the fed funds rate (ffr) is 4.4800. Cash and bonds pay meaningful income, which raises the hurdle for risk assets. The curve slope of 0.3300 is slightly positive, so the model sees no inversion signal. The VIX of 15.8662 points to calm markets and little priced-in fear, which is supportive for equities but leaves little cushion if sentiment turns. Inflation (cpi_yoy) is 2.7195 and unemployment (unrate) is 4.2000. Together they describe a firm but not overheating economy, which is broadly acceptable for equities. Bonds face a "higher for longer" risk if inflation proves sticky. Gold is exposed to high yields, since it pays no income, but it offers a hedge if inflation or policy surprises.

## 2. Why these ETFs, and why not the others

Three ETFs carry weight. In the ORP, GLD is 0.3932, QQQ is 0.3472 and XLE is 0.2595. In the OCP they are 0.6110, 0.5395 and 0.4032.

- **QQQ** has the highest forecast among the broad equity funds (mu_fwd 0.2114).
- **XLE** has the highest forecast of all (0.2364). Its coefficients differ in sign from the other equity funds, so it may diversify them.
- **GLD** has a forecast of 0.1155 and likely behaves differently from equities, which is useful in a portfolio.

The other seven get zero weight. SPY (0.1533) overlaps heavily with QQQ but has a lower forecast. IWM (0.0769), VEA (0.0565) and VWO (0.0237) have much lower forecasts. AGG (0.0444), HYG (0.0496) and TIP (0.0016) offer little forecast return. With long-only constraints, the optimizer drops assets that add little return per unit of risk given the others.

## 3. Why the portfolio is leveraged

At A = 7 the OCP puts y = 1.5536 in the risky portfolio. That means 1.5536 of capital in the ORP and a RiskFree weight of -0.5536, which is borrowing at the risk-free rate. The ORP has Sharpe = 1.2848, so each unit of risk earns a high reward in the model, and the optimizer scales exposure up to match the investor's risk tolerance. Leverage raises expected return from 18.0201% to 26.4230%. It also raises standard deviation from 11.8135% to 18.3539%. The Sharpe ratio stays at 1.2848, so leverage adds no skill. It only scales both return and risk. In practice, borrowing at the risk-free rate is optimistic, because real financing costs more and carries margin-call risk.

## 4. Risks and scenarios for underperformance

- **Concentration:** three assets hold all the risk, and four of the ten ETFs (AGG, TIP, HYG, VWO) have no weight at all.
- **Tech and growth selloff:** QQQ is the largest equity position, and leverage magnifies its losses.
- **Energy reversal:** XLE's forecast of 0.2364 is below its historical mean of 0.2824, and sector returns can reverse sharply.
- **Gold drawdown:** GLD is the largest weight. Persistently high yields or a stronger dollar could hurt it.
- **Correlated stress:** if diversification fails in a selloff, the leveraged portfolio falls faster than an unleveraged one.
- **Volatility shock from a low base:** the VIX of 15.8662 leaves room to rise, and rising financing costs would also erode the leverage benefit.

## 5. Statistical honesty

Every LOO_R2 is negative, ranging from -0.0240 (AGG) to -0.0484 (VEA). Out of sample, the models predict worse than simply using the average return. The ridge coefficients are tiny (for example, SPY's y10 coefficient is 0.00030), which shows heavy shrinkage. The forecasts therefore carry little proven macro signal and may largely reflect past averages. Some forecasts also differ sharply from history, such as AGG at 0.0444 against a hist_mu of -0.0199. With only 48 monthly observations, six features and one regime from 2021 to 2024, estimation error is large. Optimizers amplify this error, which is why the weights are concentrated and the Sharpe ratio of 1.2848 is likely overstated. The committee should treat this as a hypothesis, not a forecast. It should consider smaller leverage, position caps, or blending with a diversified benchmark.