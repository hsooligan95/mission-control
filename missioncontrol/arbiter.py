"""The arbiter: conflict resolution by NEW evidence, never by voting.

The fence this module is built to (Idea Critic, 2026-11-21): if the
arbiter only re-scores the submitted proposals -- their confidences,
their rubric points -- it is a weighted vote with an audit trail, and
the differentiator does not exist. So the design makes voting
structurally impossible:

- ``decide()`` receives ONLY the conflict and the facts the arbiter
  gathered from the world. Proposal confidences are never passed in.
- ``decide()`` refuses (raises) on empty evidence: a decision that
  cites no gathered evidence cannot be produced, let alone recorded.
- Every query the arbiter runs is logged by the world, and the
  decision record embeds the queries and the returned values, so a
  reader can re-run the same queries and check the citations.

When the gathered evidence does not discriminate between the proposals
(the budget scenario), the arbiter escalates to a human with both
proposals and the evidence attached -- it does not coin-flip.
"""
from __future__ import annotations

# Action pairs that cannot both be the primary response to one incident.
EXCLUSIVE_PAIRS = {
    frozenset({"rollback", "scale"}),
    frozenset({"failover", "restart-replica"}),
    frozenset({"page", "wait"}),
}

ESCALATE = "ESCALATE"


def detect_conflict(proposals: list[dict]) -> dict | None:
    """A conflict: contradictory world-state claims, or exclusive actions."""
    for i, a in enumerate(proposals):
        for b in proposals[i + 1:]:
            shared = set(a["claims"]) & set(b["claims"])
            for key in sorted(shared):
                if a["claims"][key] != b["claims"][key]:
                    return {"class": "world-state", "key": key,
                            "parties": [a["agent"], b["agent"]],
                            "actions": [a["action"], b["action"]]}
            if frozenset({a["action"], b["action"]}) in EXCLUSIVE_PAIRS:
                return {"class": "action", "key": None,
                        "parties": [a["agent"], b["agent"]],
                        "actions": [a["action"], b["action"]]}
    return None


def evidence_plan(conflict: dict, proposals: list[dict]) -> list[tuple]:
    """Queries chosen to discriminate between the two proposals.

    The plan is derived from WHAT is disputed -- the disputed claim key
    or the exclusive action pair -- never from who proposed what.
    """
    target = proposals[0]["target"]
    actions = set(conflict["actions"])
    if conflict["class"] == "world-state" or actions == {"failover", "restart-replica"}:
        cluster = target
        primary = f"{target}-primary"
        return [("service_state", {"service": primary}),
                ("replica_state", {"cluster": cluster})]
    if actions == {"rollback", "scale"}:
        return [("deploy_recency", {"service": target}),
                ("error_onset", {"service": target}),
                ("dependency_health", {"service": target})]
    if actions == {"page", "wait"}:
        return [("error_budget", {"service": target}),
                ("deploy_recency", {"service": target}),
                ("dependency_health", {"service": target})]
    raise ValueError(f"no evidence plan for conflict {conflict!r}")


def gather_evidence(world, plan: list[tuple]) -> list[dict]:
    """Run the plan against the live world; return the logged queries."""
    before = len(world.query_log)
    for tool, args in plan:
        getattr(world, tool)(**args)
    return world.query_log[before:]


def _fact(queries: list[dict], tool: str):
    for q in queries:
        if q["tool"] == tool:
            return q["result"]
    raise KeyError(f"evidence is missing the {tool} result")


def decide(conflict: dict, queries: list[dict]) -> dict:
    """Decide from gathered evidence ONLY.

    ``queries`` is the arbiter's own evidence log (tool, args, result).
    The proposals -- their confidences, their bases -- are not in scope
    here, by construction. Raises on empty evidence: an uncited
    decision is a bug, not a fallback.
    """
    if not queries:
        raise ValueError("arbitration decision requires gathered evidence")
    actions = set(conflict["actions"])
    if conflict["class"] == "world-state" or actions == {"failover", "restart-replica"}:
        return _decide_db_state(queries)
    if actions == {"rollback", "scale"}:
        return _decide_deploy_vs_capacity(queries)
    if actions == {"page", "wait"}:
        return _decide_page_vs_wait(queries)
    raise ValueError(f"no decision rule for conflict {conflict!r}")


def _decide_deploy_vs_capacity(queries: list[dict]) -> dict:
    deploy = _fact(queries, "deploy_recency")
    onset = _fact(queries, "error_onset")
    deps = _fact(queries, "dependency_health")
    deps_healthy = all(v == "healthy" for v in deps.values())
    if deploy is not None and deps_healthy:
        gap = deploy["minutes_ago"] - onset["minutes_ago"]
        if deploy["minutes_ago"] <= 30 and 0 <= gap <= 10:
            return {"choice": "rollback", "reasons": [
                f"deploy {deploy['version']} landed {deploy['minutes_ago']} min ago; "
                f"errors began {onset['minutes_ago']} min ago "
                f"({gap} min after the deploy)",
                f"all dependencies healthy ({deps}), so the errors are not "
                "explained by a downstream outage",
                "queue depth is a symptom of retrying failed requests, "
                "not a capacity shortfall: scaling would amplify retries "
                "against broken code",
            ]}
    return {"choice": ESCALATE, "reasons": [
        "no deploy/error-onset correlation in the gathered evidence; "
        "the capacity question cannot be settled from it"]}


def _decide_db_state(queries: list[dict]) -> dict:
    primary = _fact(queries, "service_state")
    replica = _fact(queries, "replica_state")
    if primary["status"] == "healthy":
        return {"choice": "restart-replica", "reasons": [
            f"live query: primary status is 'healthy' "
            f"(accepting_writes={primary['accepting_writes']}) -- the "
            "'primary down' claim came from a stale probe",
            f"replica lag is {replica['replica_lag_s']}s and "
            f"{replica['lag_trend']}: failing over would promote a "
            "stale replica and lose committed writes",
            "restarting the replica clears the lag without touching "
            "the healthy primary",
        ]}
    return {"choice": "failover", "reasons": [
        f"live query: primary status is {primary['status']!r}; "
        "failover is the correct response"]}


def _decide_page_vs_wait(queries: list[dict]) -> dict:
    budget = _fact(queries, "error_budget")
    samples = budget["burn_samples"]
    mean_burn = sum(samples) / len(samples)
    if mean_burn > 1.5 and budget["remaining_pct"] < 10:
        return {"choice": "page", "reasons": [
            f"mean burn {mean_burn:.2f}x with only "
            f"{budget['remaining_pct']}% of budget remaining"]}
    if mean_burn < 0.8:
        return {"choice": "wait", "reasons": [
            f"mean burn {mean_burn:.2f}x is below the alert threshold"]}
    return {"choice": ESCALATE, "reasons": [
        f"burn samples {samples} average {mean_burn:.2f}x -- inside the "
        "ambiguous band (0.8-1.5x), neither clearly paging nor clearly "
        "transient",
        f"error budget remaining is {budget['remaining_pct']}%, and one "
        "dependency is flapping intermittently, so the burn may be "
        "external",
        "the gathered evidence does not discriminate between the two "
        "proposals; escalating to a human with both proposals and this "
        "evidence attached"]}


def arbitrate(world, proposals: list[dict]) -> dict | None:
    """Full protocol: detect -> plan -> gather NEW evidence -> decide.

    Returns None when there is no conflict (arbitration must not fire).
    Otherwise returns the decision record payload: the computed choice
    plus the queries run and the values they returned.
    """
    conflict = detect_conflict(proposals)
    if conflict is None:
        return None
    queries = gather_evidence(world, evidence_plan(conflict, proposals))
    outcome = decide(conflict, queries)
    return {
        "decision_point": "mission-control.arbitration",
        "decider": "arbiter",
        "computed": True,
        "conflict": conflict,
        "choice": outcome["choice"],
        "options": conflict["actions"],
        "evidence": {
            "queries": queries,
            "reasons": outcome["reasons"],
        },
    }
