"""YOUR PoC PIPELINE — this is the file your group owns.

Lab contract = 5 automated steps, run by `python -m src.main ...`:
    01 load      input + provenance check (manifest.csv)
    02 process   your algorithm / model (the research part)
    03 rank      prioritise for a fixed review budget B
    04 review    human-in-the-loop: queue -> reviewer decisions -> overrides + audit log
    05 decide    GO / HOLD / REWORK (or track equivalent) with reason_code + owner, write outputs

Required output: out/<pred_file> with the columns listed for your track in
docs/tracks/TXX.md (also in src/metrics/tracks.py::TRACKS). Then evaluate with
    python -m src.evaluate --track tXX --pred out/<pred_file>

Rules: never read fixtures/*/gt/ here (the GT guard will stop you); seed everything via ctx.rng;
no network calls; fail loudly on missing models instead of downloading.
See src/examples/random_baseline.py for a minimal end-to-end wiring example.
"""
from __future__ import annotations

import json

import pandas as pd
import yaml

from .common.context import RunContext
from .common.decision import Decision, write_decision
from .common.manifest import verify_manifest
from .common.review import load_review_decisions, make_review_queue, write_review_queue
from .metrics.tracks import get_track
from .privacy_gate import decide_case


# ---------------------------------------------------------------- 01 load
def load(ctx: RunContext) -> dict:
    manifest = ctx.input_dir / "manifest.csv"
    problems = verify_manifest(manifest) if manifest.exists() else [{"problem": "no_manifest"}]
    if problems:
        ctx.audit.log(actor="pipeline", action="provenance_problems", item_id=str(manifest), after=problems[:20])
        if ctx.config.get("strict_provenance", True):
            raise ValueError(f"provenance check failed ({len(problems)} problems), first: {problems[:3]}")
    data = {"manifest": pd.read_csv(manifest) if manifest.exists() else None}
    if ctx.track == "t09":
        case_dir = ctx.input_dir / "cases"
        case_paths = sorted(case_dir.glob("*.json"))
        if not case_paths:
            raise ValueError(f"no privacy cases found in {case_dir}")
        cases = [json.loads(path.read_text(encoding="utf-8")) for path in case_paths]
        case_ids = [case.get("case_id") for case in cases]
        if any(not case_id for case_id in case_ids) or len(case_ids) != len(set(case_ids)):
            raise ValueError("privacy cases must have non-empty, unique case_id values")
        policy_path = ctx.input_dir / ctx.param("policy_file", "rules/policy_example.yaml")
        if not policy_path.is_file():
            raise FileNotFoundError(f"privacy policy not found: {policy_path}")
        policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
        if not isinstance(policy, dict):
            raise ValueError(f"invalid privacy policy document: {policy_path}")
        data.update(cases=cases, policy=policy)
    # TODO: load the tables/images your track needs, e.g.
    # data["images"] = pd.read_csv(ctx.input_dir / "images.csv")
    return data


# ---------------------------------------------------------------- 02 process
def process(ctx: RunContext, data: dict) -> pd.DataFrame:
    spec = get_track(ctx.track)
    if ctx.track == "t09":
        rows = []
        for case in data["cases"]:
            decision = decide_case(case, data["policy"])
            rows.append({
                "case_id": case["case_id"],
                "market": case.get("market", ""),
                **decision,
                "reason": decision["reason_codes"].replace(";", "; "),
                "review_required": decision["decision"] != "GO" or "NO_MARKET_RULES" in decision["risk_flags"],
                "policy_version": data["policy"].get("policy_version", "unspecified"),
                "case_notes": case.get("ambiguity_notes", ""),
            })
        return pd.DataFrame(rows)
    raise NotImplementedError(
        f"Implement process() for {spec.track} ({spec.title}). It must produce a DataFrame with at least "
        f"{spec.pred_columns} (saved as out/{spec.pred_file}). See docs/tracks/{spec.track.upper()}.md"
    )


# ---------------------------------------------------------------- 03 rank
def rank(ctx: RunContext, scored: pd.DataFrame) -> pd.DataFrame:
    """Default: top-B by `score`. Adapt id/score/reason columns to your track."""
    budget = int(ctx.param("budget", 20))
    if "score" not in scored.columns:
        raise ValueError("rank(): process() output needs a numeric `score` column (higher = review first), "
                         "or adapt rank() to your track")
    q = make_review_queue(scored, id_col=scored.columns[0], score_col="score", budget=budget,
                          reason_col="reason" if "reason" in scored.columns else None)
    write_review_queue(q, ctx.out("review_queue.csv"))
    return q


# ---------------------------------------------------------------- 04 review
def review(ctx: RunContext, scored: pd.DataFrame, queue: pd.DataFrame) -> pd.DataFrame:
    """If a reviewed queue exists (out/review_queue_reviewed.csv), apply it. Otherwise pass through.

    TODO: decide what an `edit` / `reject` means for your track and apply it
    (e.g. via common.review.apply_overrides), logging every change to ctx.audit.
    """
    reviewed_path = ctx.output_dir / "review_queue_reviewed.csv"
    if reviewed_path.exists():
        reviewed = load_review_decisions(reviewed_path)
        ctx.stats["n_reviewed"] = len(reviewed)
        # TODO: apply overrides
    return scored


# ---------------------------------------------------------------- 05 decide
def decide(ctx: RunContext, final: pd.DataFrame) -> Decision:
    if ctx.track == "t09":
        statuses = set(final["decision"])
        status = "HOLD" if "HOLD" in statuses else "REWORK" if "REWORK" in statuses else "GO"
        reason_code = "CASE_RISK_REQUIRES_REVIEW" if status != "GO" else "NO_MATCHING_RISK"
        return Decision(
            status=status,
            reason_code=reason_code,
            reason=f"T09 policy review summary: {len(final)} cases; {int(final.review_required.sum())} require legal/privacy review.",
            owner=ctx.config.get("owner", "TODO-owner"),
            scope=ctx.track,
            evidence=[str(ctx.input_dir / ctx.param("policy_file", "rules/policy_example.yaml")),
                      str(ctx.output_dir / get_track(ctx.track).pred_file)],
            metrics={"cases": len(final), "review_required": int(final.review_required.sum())},
        )
    # TODO: replace with your policy (thresholds frozen BEFORE looking at eval results)
    return Decision(status="HOLD", reason_code="POLICY_NOT_IMPLEMENTED", reason="Decision policy not implemented yet",
                    owner=ctx.config.get("owner", "TODO-owner"), scope=ctx.track)


def run(ctx: RunContext) -> None:
    spec = get_track(ctx.track)
    data = load(ctx)
    scored = process(ctx, data)
    ctx.stats["n_items"] = len(scored)
    queue = rank(ctx, scored)
    final = review(ctx, scored, queue)
    final[spec.pred_columns + [c for c in final.columns if c not in spec.pred_columns]].to_csv(ctx.out(spec.pred_file), index=False)
    write_decision(decide(ctx, final), ctx.out("decision.json"), ctx.out("decision_log.csv"))
