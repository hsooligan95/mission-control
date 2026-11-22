#!/usr/bin/env python3
"""Run the MissionControl scenario suite and record it in AgentTrace.

Usage: python run_mission_control.py [--seed N] [--out DIR]

Runs all four scenarios (3 conflict classes + 1 control) against the
deterministic simulated world, prints the run as it happens -- task
cards, proposals, conflicts, the arbiter's evidence queries and its
decision record, execution, verification -- then writes:
  output/report.md            the human-readable run report
  output/agenttrace-store.jsonl  the suite in the AgentTrace store
  output/timeline.md          the store, rendered by AgentTrace itself
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from missioncontrol import trace_emit
from missioncontrol.runner import run_scenario
from missioncontrol.scenarios import SCENARIOS

ROOT = Path(__file__).resolve().parent


def describe(agent: str, type_: str, payload: dict, kind: str = "event") -> None:
    if type_ == "task_card":
        print(f"  -> task card [{payload['task_id']}] to {agent}: "
              f"{payload['goal'][:72]}...")
    elif type_ == "proposal":
        print(f"  <- {agent} proposes {payload['action'].upper()} "
              f"(confidence {payload['confidence']}): {payload['basis']}")
    elif type_ == "conflict_detected":
        print(f"  !! CONFLICT ({payload['class']}): "
              f"{' vs '.join(payload['actions'])} "
              f"from {' vs '.join(payload['parties'])}")
    elif type_ == "arbitration":
        print(f"  ** ARBITER gathered NEW evidence:")
        for q in payload["evidence"]["queries"]:
            print(f"       query {q['tool']}({q['args']}) -> "
                  f"{json.dumps(q['result'])}")
        print(f"  ** DECISION: {payload['choice'].upper()}")
        for reason in payload["evidence"]["reasons"]:
            print(f"       - {reason}")
    elif type_ == "agreement":
        print(f"  == proposals agree on {payload['action'].upper()}; "
              "arbitration did not fire")
    elif type_ == "action_executed":
        print(f"  >> executed {payload['action'].upper()} on "
              f"{payload['target']}")
    elif type_ == "verification":
        print(f"  >> verify: {'RESOLVED' if payload['resolved'] else 'UNRESOLVED'}")
    elif type_ == "escalated":
        print("  >> ESCALATED to a human (no action executed)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", type=Path, default=ROOT / "output")
    args = parser.parse_args()

    print("MissionControl — multi-agent incident response")
    print("=" * 60)
    results = []
    for scenario in SCENARIOS:
        print(f"\n[{scenario['id']}] {scenario['title']}")
        results.append(run_scenario(scenario, emit=describe))
        print(f"  == outcome: {results[-1]['outcome'].upper()}")

    args.out.mkdir(parents=True, exist_ok=True)
    store_path = args.out / "agenttrace-store.jsonl"
    store_path.unlink(missing_ok=True)
    trace_id = f"trace-missioncontrol-{args.seed}"
    info = trace_emit.emit_suite(store_path, results,
                                 seed=args.seed, trace_id=trace_id)
    timeline = trace_emit.render_store_timeline(store_path)
    (args.out / "timeline.md").write_text(timeline, encoding="utf-8")

    report = ["# MissionControl — suite run report", "",
              f"Trace ID: `{trace_id}` · {info['events']} events in the "
              "AgentTrace store · chain verified by the renderer below.", ""]
    for r in results:
        s = r["scenario"]
        report += [f"## {s['id']} — {s['title']}", "",
                   f"*{s['class']}*", "", f"Incident: {s['incident']}", ""]
        for p in r["proposals"]:
            report.append(f"- **{p['agent']}** proposes "
                          f"**{p['action']}** (confidence "
                          f"{p['confidence']}): {p['basis']}")
        if r["decision"]:
            report += ["", "**Arbiter decision record:**", "",
                       "```json",
                       json.dumps(r["decision"], indent=2),
                       "```", ""]
        report += [f"Outcome: **{r['outcome']}**", ""]
    report += ["## Timeline (rendered from the AgentTrace store)", "",
               timeline]
    (args.out / "report.md").write_text("\n".join(report), encoding="utf-8")

    print("\n" + "=" * 60)
    print(f"Suite recorded: {info['events']} events under {trace_id}")
    print(f"Store: {store_path}")
    print(f"Report: {args.out / 'report.md'}")


if __name__ == "__main__":
    main()
