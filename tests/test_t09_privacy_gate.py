import pandas as pd
import pytest

from src import main as runner
from src.privacy_gate import matches


def test_t09_writes_all_case_decisions_and_flags_cross_border(tmp_path):
    out = tmp_path / "out"
    rc = runner.main([
        "--track", "t09",
        "--input", "fixtures/t09_privacy_gate",
        "--output", str(out),
        "--offline",
    ])
    assert rc == 0

    decisions = pd.read_csv(out / "decisions.csv").set_index("case_id")
    assert len(decisions) == 12
    assert decisions.loc["CASE-02", "decision"] == "HOLD"
    assert "XBORDER_NO_MECHANISM" in decisions.loc["CASE-02", "reason_codes"]
    assert "CROSS_BORDER_TRANSFER" in decisions.loc["CASE-02", "risk_flags"]
    assert "XBORDER_NO_IMPACT_ASSESSMENT" in decisions.loc["CASE-07", "reason_codes"]
    assert decisions.loc["CASE-10", "decision"] == "GO"
    assert decisions.loc["CASE-12", "decision"] == "HOLD"
    assert decisions.loc["CASE-05", "decision"] == "REWORK"
    assert decisions.index.name == "case_id"
    assert {"decision", "reason_codes"}.issubset(decisions.columns)


def test_t09_policy_conditions_do_not_execute_python():
    with pytest.raises(ValueError, match="unsupported policy expression"):
        matches("__import__('os').system('echo unsafe')", {})


def test_t09_naive_baseline_runs_and_misses_cross_border_risk(tmp_path):
    out = tmp_path / "baseline"
    rc = runner.main([
        "--track", "t09",
        "--pipeline", "src.examples.t09_consent_baseline",
        "--input", "fixtures/t09_privacy_gate",
        "--output", str(out),
        "--offline",
    ])
    assert rc == 0

    decisions = pd.read_csv(out / "decisions.csv").set_index("case_id")
    assert len(decisions) == 12
    assert decisions.loc["CASE-02", "decision"] == "GO"
    assert decisions.loc["CASE-07", "decision"] == "GO"
    assert decisions.loc["CASE-08", "decision"] == "HOLD"
