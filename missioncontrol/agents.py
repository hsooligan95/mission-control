"""Stub specialist agents.

Each agent is a small deterministic rule over a partial *view* of the
incident -- the signals that persona would plausibly have (a runbook, a
probe result, a queue graph). Agents never see the world itself, and
their views can be stale or wrong; that is what makes their conflicts
real instead of choreographed agreement.

A proposal carries the agent's claims about the world and a confidence.
The confidence is part of the proposal record for audit -- and the
arbiter is built so it cannot use it (see arbiter.decide, which never
receives the proposals' scores).
"""
from __future__ import annotations

AGENT_CARDS = {
    "triage": {
        "name": "triage",
        "role": "Classify the incident, match the runbook, route the task.",
        "skills": ["runbook-matching", "severity-classification"],
    },
    "diagnose": {
        "name": "diagnose",
        "role": "Investigate with probes and metrics; find the mechanism.",
        "skills": ["metrics-analysis", "probe-execution"],
    },
    "remediate": {
        "name": "remediate",
        "role": "Propose and execute the remediation action.",
        "skills": ["action-execution", "state-verification"],
    },
    "verify": {
        "name": "verify",
        "role": "Check post-action state against the resolution criteria.",
        "skills": ["state-verification"],
    },
}


def _proposal(agent: str, view: dict) -> dict:
    return {
        "agent": agent,
        "action": view["propose_action"],
        "target": view["target"],
        "claims": view.get("claims", {}),
        "confidence": view["confidence"],
        "basis": view["basis"],
    }


def triage_agent(view: dict) -> dict:
    """Runbook persona: proposes the action its matched runbook prescribes."""
    return _proposal("triage", view)


def diagnose_agent(view: dict) -> dict:
    """Investigation persona: proposes from its probes/metrics snapshot."""
    return _proposal("diagnose", view)


def remediate_agent(view: dict) -> dict:
    """Execution persona: proposes the action it judges safest to run."""
    return _proposal("remediate", view)


def verify_agent(world, checks: list[dict]) -> dict:
    """Run the scenario's resolution checks against live post-action state."""
    results = [{"check": c, "passed": world.check(c)} for c in checks]
    return {"agent": "verify",
            "resolved": all(r["passed"] for r in results),
            "results": results}
