from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
report = (ROOT / "make_report.py").read_text()
qa = (ROOT / "docs/deliverables/qa_cheatsheet.md").read_text()


def test_no_claim_that_solver_agreement_has_already_happened():
    assert "independent Python and Excel Solver cross-checks" not in report
    assert "Excel Solver, Python and the LLM's code all agree" not in qa
    assert "Solver run" in qa


def test_risk_free_convention_and_sensitivity_are_disclosed():
    assert "2021-24 average risk-free rate" in report
    assert "2021-24 average risk-free rate" in qa


def test_shrinkage_and_weight_gap_wording():
    assert "heavily shrunk" in report
    assert "about 3 points" in report and "about 2 points" not in report
    assert "about 3 points" in qa or "about 2 points" not in qa


def test_collapse_rate_is_also_reported_at_a_one_percent_threshold():
    assert "1% threshold" in report
