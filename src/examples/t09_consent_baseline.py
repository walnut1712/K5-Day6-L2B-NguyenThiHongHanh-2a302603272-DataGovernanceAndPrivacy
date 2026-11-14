"""Intentionally naive T09 baseline: GO when consent or any known basis is present."""
from __future__ import annotations

import pandas as pd

from ..common.context import RunContext
from ..common.decision import Decision, write_decision
from ..metrics.tracks import get_track
from ..pipeline import load


def run(ctx: RunContext) -> None:
    data = load(ctx)
    rows = []
    for case in data["cases"]:
        has_evidence = case["consent"]["obtained"] or case["lawful_basis"] != "unknown"
        rows.append({
            "case_id": case["case_id"],
            "decision": "GO" if has_evidence else "HOLD",
            "reason_codes": "BASELINE_KNOWN_BASIS" if has_evidence else "BASELINE_UNKNOWN_BASIS",
        })

    spec = get_track(ctx.track)
    decisions = pd.DataFrame(rows)
    decisions.to_csv(ctx.out(spec.pred_file), index=False)
    ctx.stats["n_items"] = len(decisions)
    write_decision(
        Decision(
            status="HOLD",
            reason_code="BASELINE_ONLY",
            reason="Naive T09 baseline; not a legal approval or release decision.",
            owner=ctx.config.get("owner", "baseline"),
            scope=ctx.track,
            evidence=[str(ctx.out(spec.pred_file))],
            metrics={"cases": len(decisions)},
        ),
        ctx.out("decision.json"),
        ctx.out("decision_log.csv"),
    )
