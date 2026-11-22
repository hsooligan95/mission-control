# Copilot instructions — mission-control

You are working in **MissionControl**, multi-agent incident response
where disagreements between specialist agents are resolved by an arbiter
that gathers NEW evidence from the environment — never by voting.

## Stack

- Python 3; package `missioncontrol/` (world, agents, arbiter,
  scenarios, runner, trace_emit). Deterministic simulated environment,
  stub agents, no API keys, runs offline in under a minute.
- Entry: `run_mission_control.py` (full scenario suite).

## Tests

```bash
python -m pytest   # 14 tests
```

## Architecture notes

- The arbiter's `decide()` receives ONLY the conflict and the evidence
  log — proposal confidences are never in scope, so weighted voting is
  impossible by construction. Do not widen that signature.
- `decide()` raises on an empty evidence log: an uncited decision must
  be unproducible. Every decision record cites the exact queries and
  values that decided it.
- Escalation is a valid outcome: when gathered evidence doesn't
  discriminate, the arbiter escalates and nothing executes.
- Each conflict scenario class (rollback-vs-scale, restart-vs-failover,
  page-vs-wait) carries a written `losing_defense` in `scenarios.py` —
  the ambiguity screen. A new scenario without one doesn't merge. The
  control case (agents agree) must show zero arbiter queries.
- Runs emit AgentTrace schema v1 events under one trace ID; arbitration
  outcomes are computed decision points, so they are decision records.

## Shared rules

- Use Unix LF line endings in every file; never CRLF.
- Never commit secrets, tokens, or credentials — real or synthetic-looking.
- Tests must pass before you describe a change as complete; run the test
  command above and report honestly if you cannot.
- Prefer the smallest complete implementation: reuse what already exists in
  this repo before adding new code, files, or dependencies.
