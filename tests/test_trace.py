"""AgentTrace integration: the suite lands in the store, verifiably."""
import sys
from pathlib import Path

PORTFOLIO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PORTFOLIO / "agent-trace"))

from agenttrace.store import load_events, verify  # noqa: E402

from missioncontrol import trace_emit  # noqa: E402
from missioncontrol.runner import run_suite  # noqa: E402
from missioncontrol.scenarios import SCENARIOS  # noqa: E402

TRACE_ID = "trace-missioncontrol-test"


def _emit(tmp_path):
    store = tmp_path / "store.jsonl"
    results = run_suite(SCENARIOS)
    info = trace_emit.emit_suite(store, results, seed=7, trace_id=TRACE_ID)
    return store, info


def test_suite_lands_in_store_under_one_trace_id(tmp_path):
    store, info = _emit(tmp_path)
    events = load_events(store)
    assert info["events"] == len(events)
    assert {e["trace_id"] for e in events} == {TRACE_ID}
    assert {e["source"] for e in events} == {"mission-control"}
    assert verify(store).ok


def test_arbitration_decision_records_in_store_cite_evidence(tmp_path):
    store, _ = _emit(tmp_path)
    records = [e for e in load_events(store)
               if e["kind"] == "decision_record"
               and e["payload"]["decision_point"] == "mission-control.arbitration"]
    assert len(records) == 3  # 3 conflict scenarios; the control has none
    for record in records:
        assert record["payload"]["evidence"]["queries"]


def test_timeline_renders_from_store_alone(tmp_path):
    store, _ = _emit(tmp_path)
    timeline = trace_emit.render_store_timeline(store)
    assert "Chain OK" in timeline
    assert "mission-control.arbitration" in timeline


def test_suite_is_deterministic(tmp_path):
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    for store in (a, b):
        trace_emit.emit_suite(store, run_suite(SCENARIOS),
                              seed=7, trace_id=TRACE_ID)
    assert a.read_bytes() == b.read_bytes()
