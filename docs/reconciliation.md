# Excel vs Python reconciliation

## Formula check (done)
The workbook was opened in Microsoft Excel (v16.100) and values were read live from the open file.
Excel's S6 statistics (annualised return, st. dev., Sharpe, Rf) and S7 covariance matrix match Python to < 1e-14.
Excel's S8 MVP, ORP and OCP quantities (return, st. dev., Sharpe, y, closed-form y*) and all 80 frontier st. devs
match Python to < 1e-12 (`python tests/reconcile.py --live` prints ALL OK).
Note: with the pre-filled (Python) weights this proves the formulas, not Solver itself.

## Solver check (PENDING: needs the user in Excel)
1. Open `FIN3702B_SolverTest.xlsx` (weights start at 1/10 and y = 0.5).
2. S8_Solver: run Solver for MVP, ORP, OCP using the instructions in rows 33-37. Save the file.
3. `python tests/reconcile.py FIN3702B_SolverTest.xlsx` should print ALL OK (tolerance 0.005 absolute).
