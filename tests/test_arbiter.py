"""The arbiter's fences: evidence or nothing, and never a vote."""
import copy

import pytest

from missioncontrol.arbiter import arbitrate, decide, detect_conflict
from missioncontrol.runner import run_scenario
from missioncontrol.scenarios import SCENARIOS
from missioncontrol.world import World

BY_ID = {s["id"]: s for s in SCENARIOS}


def _proposals(scenario):
    return [{"agent": name, "action": v["propose_action"],
             "target": v["target"], "claims": v.get("claims", {}),
             "confidence": v["confidence"], "basis": v["basis"]}
            for name, v in scenario["views"].items()]


def test_decide_refuses_empty_evidence():
    conflict = {"class": "action", "key": None,
                "parties": ["diagnose", "triage"],
                "actions": ["scale", "rollback"]}
    with pytest.raises(ValueError):
        decide(conflict, [])


def test_conflict_classes_detected():
    assert detect_conflict(_proposals(BY_ID["rollback-vs-scale"]))["class"] == "action"
    assert detect_conflict(_proposals(BY_ID["restart-vs-failover"]))["class"] == "world-state"
    assert detect_conflict(_proposals(BY_ID["page-vs-wait"]))["class"] == "action"
    assert detect_conflict(_proposals(BY_ID["control-agreement"])) is None


def test_decision_is_not_a_confidence_vote():
    """The losing proposal has the HIGHER confidence (0.8 scale vs 0.6
    rollback). If the arbiter weighted confidences, scale would win."""
    scenario = BY_ID["rollback-vs-scale"]
    world = World(scenario["world"], scenario["effects"])
    decision = arbitrate(world, _proposals(scenario))
    assert decision["choice"] == "rollback"


def test_flipping_confidences_changes_nothing():
    scenario = copy.deepcopy(BY_ID["rollback-vs-scale"])
    for view in scenario["views"].values():
        view["confidence"] = 1.0 - view["confidence"]
    world = World(scenario["world"], scenario["effects"])
    decision = arbitrate(world, _proposals(scenario))
    assert decision["choice"] == "rollback"


def test_every_decision_cites_gathered_evidence():
    """Fails if any arbitration decision cites no gathered evidence --
    and checks the cited values against the world's actual values."""
    for scenario in SCENARIOS:
        result = run_scenario(scenario)
        if result["decision"] is None:
            continue
        queries = result["decision"]["evidence"]["queries"]
        assert queries, f"{scenario['id']}: decision cites no evidence"
        fresh = World(scenario["world"], scenario["effects"])
        for q in queries:
            actual = getattr(fresh, q["tool"])(**q["args"])
            assert actual == q["result"], (
                f"{scenario['id']}: cited {q['tool']} result does not "
                "match the world's actual value")


def test_arbiter_acquires_evidence_neither_proposer_submitted():
    """The discriminating facts (deploy recency, error onset) appear in
    no proposal's basis or claims -- the arbiter had to go and get them."""
    scenario = BY_ID["rollback-vs-scale"]
    world = World(scenario["world"], scenario["effects"])
    decision = arbitrate(world, _proposals(scenario))
    tools = {q["tool"] for q in decision["evidence"]["queries"]}
    assert {"deploy_recency", "error_onset", "dependency_health"} <= tools
