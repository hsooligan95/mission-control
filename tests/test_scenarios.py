"""One test per scenario: 3 conflict classes + the control."""
from missioncontrol.runner import run_scenario
from missioncontrol.scenarios import SCENARIOS

BY_ID = {s["id"]: s for s in SCENARIOS}


def test_rollback_vs_scale__action_conflict():
    r = run_scenario(BY_ID["rollback-vs-scale"])
    assert r["conflict"]["class"] == "action"
    assert r["decision"]["choice"] == "rollback"
    assert r["outcome"] == "resolved"
    # The executed rollback actually fixed the world.
    assert r["world"].service_state("checkout-api")["version"] == "v2.4.0"


def test_restart_vs_failover__world_state_conflict():
    r = run_scenario(BY_ID["restart-vs-failover"])
    assert r["conflict"]["class"] == "world-state"
    assert r["conflict"]["key"] == "orders-db.primary_status"
    assert r["decision"]["choice"] == "restart-replica"
    assert r["outcome"] == "resolved"
    # The healthy primary was never demoted.
    assert r["world"].service_state(
        "orders-db-primary")["accepting_writes"] is True


def test_page_vs_wait__tie_escalates():
    r = run_scenario(BY_ID["page-vs-wait"])
    assert r["decision"]["choice"] == "ESCALATE"
    assert r["outcome"] == "escalated"
    # Escalation executed nothing: the world is untouched.
    assert r["world"].service_state("search-api")["error_rate"] == 0.04


def test_control__agreement_no_arbitration():
    r = run_scenario(BY_ID["control-agreement"])
    assert r["conflict"] is None
    assert r["decision"] is None
    assert r["outcome"] == "resolved"
    # Proof the arbiter never ran: it made zero evidence queries.
    assert r["world"].query_log == []
