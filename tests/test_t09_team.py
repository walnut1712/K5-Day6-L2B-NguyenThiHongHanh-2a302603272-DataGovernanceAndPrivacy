"""Team tests for T09 Privacy Decision Gate (success + failure/edge)."""
import pandas as pd
import pytest

from src import main as runner
from src.privacy_gate import decide_case, matches

BASE = ["--track", "t09", "--offline", "--seed", "42"]


def run_poc(out):
    return runner.main(BASE + ["--output", str(out)])


def test_crossborder_cases_are_held(tmp_path):
    """Success: failure mode of the consent-only baseline. CASE-02 and CASE-07 must HOLD with the cross-border flag."""
    assert run_poc(tmp_path) == 0
    d = pd.read_csv(tmp_path / "decisions.csv").set_index("case_id")
    for cid in ("CASE-02", "CASE-07"):
        assert d.loc[cid, "decision"] == "HOLD"
        assert "CROSS_BORDER_TRANSFER" in d.loc[cid, "risk_flags"]


def test_market_without_rules_is_flagged_for_review(tmp_path):
    """Success: IN has no market rules, so it must carry NO_MARKET_RULES and need review."""
    assert run_poc(tmp_path) == 0
    d = pd.read_csv(tmp_path / "decisions.csv").set_index("case_id")
    assert "NO_MARKET_RULES" in d.loc["CASE-09", "risk_flags"]
    assert bool(d.loc["CASE-09", "review_required"]) is True


def test_missing_input_fails_clearly(tmp_path):
    """Failure: a missing input directory must fail with a clear non-zero exit code, not crash silently."""
    rc = runner.main(BASE + ["--input", str(tmp_path / "does_not_exist"), "--output", str(tmp_path / "out")])
    assert rc != 0


def test_malicious_policy_condition_is_rejected():
    """Edge: the rule language must never execute arbitrary code."""
    with pytest.raises(ValueError):
        matches("__import__('os').system('echo hacked')", {})


def test_case_with_missing_fields_does_not_crash():
    """Edge: a case without transfer/storage fields is evaluated, not crashed on."""
    policy = {"rules": [{
        "id": "R-T", "markets": ["*"], "when": "transfer.cross_border and not transfer.mechanism",
        "decision": "HOLD", "reason_code": "XBORDER_NO_MECHANISM", "source": {"doc": "test", "ref": "test"},
    }]}
    out = decide_case({"case_id": "X", "market": "VN"}, policy)
    assert out["decision"] == "GO"
    assert "NO_MARKET_RULES" in out["risk_flags"]


def test_review_decisions_are_applied_and_audited(tmp_path):
    """Success: reviewer decisions are applied and every one is written to audit_log.jsonl."""
    assert run_poc(tmp_path) == 0
    q = pd.read_csv(tmp_path / "review_queue.csv", dtype=str, keep_default_na=False)
    q["reviewer"] = "Test Reviewer"
    q["reviewer_decision"] = "approve"
    q.loc[q["item_id"] == "CASE-06", "reviewer_decision"] = "escalate"
    q["review_note"] = "test note"
    q.to_csv(tmp_path / "review_queue_reviewed.csv", index=False)
    assert run_poc(tmp_path) == 0
    log = (tmp_path / "audit_log.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(log) == len(q)
    d = pd.read_csv(tmp_path / "decisions.csv").set_index("case_id")
    assert d.loc["CASE-06", "decision"] == "GO"
    assert bool(d.loc["CASE-06", "review_required"]) is True
