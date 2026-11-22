"""AgentTrace integration: every run lands in the audit store.

A full suite run is emitted into an AgentTrace store
(~/workspace/github-portfolio/agent-trace, schema_version 1) under one
trace ID: suite start, then per scenario the task cards, proposals,
conflict, arbitration decision record, execution and verification,
and a closing decision_record carrying the suite verdict.

Arbitration decisions are decision records because they are COMPUTED
decision points: the arbiter's code branch makes the choice, at
decision time, from the evidence values that decided it -- which are
embedded in the record. No agent narration is recorded as a decision.

Timestamps are a deterministic clock, so re-running the suite
reproduces the same store byte-for-byte up to the hash chain.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PORTFOLIO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PORTFOLIO / "agent-trace"))

from agenttrace.render import render_timeline  # noqa: E402
from agenttrace.schema import new_event  # noqa: E402
from agenttrace.store import append_events, load_events, verify  # noqa: E402

SOURCE = "mission-control"
_BASE_TS = datetime(2026, 11, 21, 16, 30, tzinfo=timezone.utc)


class _Clock:
    def __init__(self) -> None:
        self._n = 0

    def next(self) -> str:
        ts = _BASE_TS + timedelta(minutes=self._n)
        self._n += 1
        return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def emit_suite(store_path: Path, results: list[dict], *, seed: int,
               trace_id: str) -> dict:
    """Run-shaped results -> AgentTrace events under one trace ID."""
    clock = _Clock()
    events: list[dict] = []

    def add(agent: str, type_: str, payload: dict, kind: str = "event"):
        events.append(new_event(
            trace_id=trace_id, ts=clock.next(), source=SOURCE,
            agent=agent, type=type_, kind=kind, payload=payload))

    add(SOURCE, "suite_started",
        {"seed": seed, "scenarios": [r["scenario"]["id"] for r in results]})
    for result in results:
        for agent, type_, payload, kind in result["log"]:
            add(agent, type_, payload, kind)
    arbitrated = [r for r in results if r["decision"] is not None]
    escalated = [r["scenario"]["id"] for r in results
                 if r["outcome"] == "escalated"]
    resolved = [r["scenario"]["id"] for r in results
                if r["outcome"] == "resolved"]
    add(SOURCE, "suite_verdict", {
        "decision_point": "mission-control.suite_verdict",
        "decider": SOURCE,
        "computed": True,
        "choice": (f"{len(resolved)}/{len(results)} incidents resolved, "
                   f"{len(escalated)} escalated, "
                   f"{len(arbitrated)} arbitrated"),
        "evidence": {"reasons": [
            *[f"{r['scenario']['id']}: {r['outcome']} "
              f"(chose {r['decision']['choice'] if r['decision'] else 'agreed action'})"
              for r in results],
        ]}}, kind="decision_record")
    append_events(store_path, events)
    return {"trace_id": trace_id, "events": len(events)}


def render_store_timeline(store_path: Path) -> str:
    events = load_events(store_path)
    result = verify(store_path)
    return render_timeline(
        events, verify_result=result,
        title="MissionControl — suite run in the AgentTrace store")
