"""Trivial T09 baseline: HOLD every case. Critical-miss = 0 but false HOLD is maximal (fails guardrail)."""
from __future__ import annotations

import pandas as pd

from .common.context import RunContext
from .common.decision import Decision, write_decision
from .metrics.tracks import get_track
from .pipeline import load


def run(ctx: RunContext) -> None:
    data = load(ctx)
    rows = [
        {
            "case_id": case["case_id"],
            "decision": "HOLD",
            "reason_codes": "BASELINE_HOLD_ALL",
        }
        for case in data["cases"]
    ]

    spec = get_track(ctx.track)
    decisions = pd.DataFrame(rows)
    decisions.to_csv(ctx.out(spec.pred_file), index=False)
    ctx.stats["n_items"] = len(decisions)
    write_decision(
        Decision(
            status="HOLD",
            reason_code="BASELINE_ONLY",
            reason="Trivial HOLD-all T09 baseline; not a legal approval or release decision.",
            owner=ctx.config.get("owner", "baseline"),
            scope=ctx.track,
            evidence=[str(ctx.out(spec.pred_file))],
            metrics={"cases": len(decisions)},
        ),
        ctx.out("decision.json"),
        ctx.out("decision_log.csv"),
    )
