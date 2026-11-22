"""The coordination layer: task cards out, proposals back, conflicts
to the arbiter, the chosen action executed, the outcome verified.

Handoffs are A2A-style task cards -- an explicit contract (goal,
evidence, constraints) with a task lifecycle (submitted -> working ->
completed) -- modeled on the core concepts of the A2A protocol, not a
spec implementation (see README Limitations). Agents communicate only
through these messages and the shared proposal record; there is no
direct agent-to-agent state passing.

Every step is reported through an ``emit`` callback so the run can be
recorded into the AgentTrace store without the runner knowing about
the store.
"""
from __future__ import annotations

from . import agents
from .arbiter import arbitrate, detect_conflict
from .world import World

AGENT_FUNCS = {"triage": agents.triage_agent,
               "diagnose": agents.diagnose_agent,
               "remediate": agents.remediate_agent}


def _noop(*_args, **_kwargs):
    pass


def run_scenario(scenario: dict, emit=_noop) -> dict:
    """Run one incident end to end; return its full record."""
    world = World(scenario["world"], scenario.get("effects"))
    sid = scenario["id"]
    log: list[tuple] = []
    callback = emit

    def _emit(agent, type_, payload, kind="event"):
        log.append((agent, type_, payload, kind))
        callback(agent, type_, payload, kind=kind)

    emit = _emit
    emit("coordinator", "run_started",
         {"scenario": sid, "title": scenario["title"],
          "incident": scenario["incident"]})

    # Task cards: coordinator -> each proposing agent.
    proposals = []
    for name, view in scenario["views"].items():
        task_id = f"{sid}:{name}"
        emit(name, "task_card",
             {"task_id": task_id, "from": "coordinator", "to": name,
              "state": "submitted",
              "goal": scenario["incident"],
              "agent_card": agents.AGENT_CARDS[name]})
        proposal = AGENT_FUNCS[name](view)
        proposals.append(proposal)
        emit(name, "proposal",
             {"task_id": task_id, "state": "completed", **proposal})
    # Handoff: the proposal record passes to the coordinator as one body.
    emit("coordinator", "handoff",
         {"task_id": f"{sid}:coordinate", "from": "agents",
          "to": "coordinator", "state": "working",
          "proposals": [p["action"] for p in proposals]})

    conflict = detect_conflict(proposals)
    decision = None
    if conflict is not None:
        emit("arbiter", "conflict_detected",
             {"scenario": sid, **conflict})
        decision = arbitrate(world, proposals)
        emit("arbiter", "arbitration", decision, kind="decision_record")
        chosen = decision["choice"]
    else:
        emit("coordinator", "agreement",
             {"scenario": sid,
              "action": proposals[0]["action"],
              "note": "proposals agree; arbitration did not fire"})
        chosen = proposals[0]["action"]

    if chosen == "ESCALATE":
        emit("coordinator", "escalated",
             {"scenario": sid,
              "note": "handed to a human with both proposals and the "
                      "arbiter's gathered evidence attached"})
        outcome = "escalated"
    else:
        world.apply_action(chosen)
        emit("remediate", "action_executed",
             {"scenario": sid, "action": chosen,
              "target": proposals[0]["target"]})
        verdict = agents.verify_agent(world, scenario["checks"])
        emit("verify", "verification",
             {"scenario": sid, **verdict})
        outcome = "resolved" if verdict["resolved"] else "unresolved"

    emit("coordinator", "run_completed",
         {"scenario": sid, "outcome": outcome,
          "chosen_action": chosen})
    return {"scenario": scenario, "proposals": proposals,
            "conflict": conflict, "decision": decision,
            "outcome": outcome, "world": world, "log": log}


def run_suite(scenarios: list[dict], emit=_noop) -> list[dict]:
    return [run_scenario(s, emit) for s in scenarios]
