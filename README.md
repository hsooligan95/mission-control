# MissionControl — multi-agent incident response, arbitrated by evidence

Specialist agents work the same incident — and when they disagree, the
system does not average their answers or weigh their confidences. An
**arbiter** goes and queries the environment for NEW evidence that
neither side submitted, decides from that evidence alone, and writes a
decision record citing the exact queries and values that decided it.

**What arbitration does that voting doesn't, in one sentence:** a vote
re-weighs what the proposers already said; this arbiter's `decide()`
function never receives the proposals at all — it takes only the
conflict and the evidence log, and it *raises* rather than decide if
that log is empty.

## The demo moment

`checkout-api` is erroring. Diagnose (confidence **0.8**) says scale —
the queue is the textbook signature of saturation. Triage (confidence
0.6) says roll back — the runbook's rule for post-deploy error spikes.
A confidence-weighted vote picks scale. The arbiter picks rollback,
because it went and looked:

```
  !! CONFLICT (action): scale vs rollback from diagnose vs triage
  ** ARBITER gathered NEW evidence:
       query deploy_recency({'service': 'checkout-api'}) -> {"version": "v2.4.1", "minutes_ago": 12, "note": "payment client retry-policy change"}
       query error_onset({'service': 'checkout-api'}) -> {"minutes_ago": 11}
       query dependency_health({'service': 'checkout-api'}) -> {"payment-gw": "healthy", "inventory-db": "healthy"}
  ** DECISION: ROLLBACK
       - deploy v2.4.1 landed 12 min ago; errors began 11 min ago (1 min after the deploy)
       - all dependencies healthy, so the errors are not explained by a downstream outage
       - queue depth is a symptom of retrying failed requests, not a capacity shortfall
  >> executed ROLLBACK on checkout-api
  >> verify: RESOLVED
```

The losing proposal is preserved in the record, with its case intact —
and the test suite proves the outcome is not a vote:
`test_decision_is_not_a_confidence_vote` (the higher-confidence
proposal loses) and `test_flipping_confidences_changes_nothing`
(swapping every confidence leaves the decision unchanged).

## The decision record

Arbitration decisions are AgentTrace `decision_record`s — computed
decision points, emitted by the code branch that made the choice, from
the values that decided it:

```json
{
  "decision_point": "mission-control.arbitration",
  "decider": "arbiter",
  "computed": true,
  "conflict": {"class": "action", "key": null,
               "parties": ["diagnose", "triage"],
               "actions": ["scale", "rollback"]},
  "choice": "rollback",
  "options": ["scale", "rollback"],
  "evidence": {
    "queries": [
      {"tool": "deploy_recency", "args": {"service": "checkout-api"},
       "result": {"version": "v2.4.1", "minutes_ago": 12,
                  "note": "payment client retry-policy change"}},
      {"tool": "error_onset", "args": {"service": "checkout-api"},
       "result": {"minutes_ago": 11}},
      {"tool": "dependency_health", "args": {"service": "checkout-api"},
       "result": {"payment-gw": "healthy", "inventory-db": "healthy"}}
    ],
    "reasons": [
      "deploy v2.4.1 landed 12 min ago; errors began 11 min ago (1 min after the deploy)",
      "all dependencies healthy, so the errors are not explained by a downstream outage",
      "queue depth is a symptom of retrying failed requests, not a capacity shortfall: scaling would amplify retries against broken code"
    ]
  }
}
```

A test re-runs every cited query against a fresh world and asserts the
cited values match the world's actual values — a decision that cites
no evidence, or cites it wrong, fails the suite.

## The scenario set

Four seeded incidents. Each conflict scenario passed an ambiguity
screen before admission: the losing proposal's defense (in
`missioncontrol/scenarios.py`) had to be writable, convincingly, from
the evidence its proposer had at decision time. If it couldn't be,
the scenario would be rigged — the arbiter "winning" against a straw
man proves nothing.

| Scenario | Class | Proposals | Arbiter's new evidence | Outcome |
|---|---|---|---|---|
| rollback-vs-scale | action conflict | scale (0.8) vs rollback (0.6) | deploy 12 min ago, errors 1 min later, deps healthy | **rollback**, resolved |
| restart-vs-failover | world-state conflict | failover ("primary down") vs restart-replica ("primary healthy") | live query: primary healthy, accepting writes; replica lag 340s | **restart-replica**, resolved — failover would have promoted a stale replica and lost committed writes |
| page-vs-wait | genuine tie | page (budget critical) vs wait (transient burn) | burn samples average 1.38× — inside the ambiguous band; one dependency flapping | **ESCALATE** to a human, both proposals + evidence attached; nothing executed |
| control-agreement | control | both propose restart | — | agreement; arbitration **did not fire** (zero evidence queries — asserted by test) |

## How it works

- **Agents** (`missioncontrol/agents.py`) — stub personas (triage,
  diagnose, remediate, verify) with agent cards. Each sees only a
  partial, sometimes stale *view* of the incident — a runbook match, a
  probe snapshot. Their conflicts come from genuinely different
  evidence, not scripted disagreement.
- **Handoffs** (`missioncontrol/runner.py`) — A2A-style task cards:
  an explicit contract (goal, evidence, constraints) with a task
  lifecycle (submitted → working → completed). Agents communicate
  only through messages and the shared proposal record.
- **The world** (`missioncontrol/world.py`) — a deterministic,
  seeded, simulated environment: service state, recent deploys,
  dependency health, error budgets, replica state. Agents never see
  it. The arbiter queries it at decision time; every query is logged.
- **The arbiter** (`missioncontrol/arbiter.py`) — conflict detection
  (contradictory world-state claims, or mutually exclusive actions),
  an evidence plan derived from *what is disputed*, evidence gathering
  against the live world, and a decision rule over the gathered facts
  only. When the facts don't discriminate, it escalates instead of
  manufacturing a winner.

## AgentTrace integration

The full suite is emitted into the AgentTrace store (schema v1) under
one trace ID — task cards, proposals, conflicts, decision records,
executions, verifications — and rendered by AgentTrace's own renderer
from the store alone:

```
trace-missioncontrol-7
├── mission-control (44 events)
│   #  9  arbitration        DECISION mission-control.arbitration: rollback (decider=arbiter, computed=True)
│   # 20  arbitration        DECISION mission-control.arbitration: restart-replica (decider=arbiter, computed=True)
│   # 31  arbitration        DECISION mission-control.arbitration: ESCALATE (decider=arbiter, computed=True)
│   # 44  suite_verdict      DECISION mission-control.suite_verdict: 3/4 incidents resolved, 1 escalated, 3 arbitrated
**Chain OK — 44 events, every hash verified.**
```

(Full timeline: `output/timeline.md` after a run.)

## Run it

```bash
python run_mission_control.py          # full suite, ~0.2s, offline, no API keys
python -m pytest                       # 14 tests
```

Outputs land in `output/`: `report.md` (run report with every decision
record), `agenttrace-store.jsonl`, `timeline.md`. Re-running produces
a byte-identical store — the suite is fully deterministic.

## Tests (14)

- **Per conflict class + control** — decision, outcome, and world
  post-conditions (the healthy primary is never demoted; escalation
  executes nothing; the control's world shows zero arbiter queries).
- **Evidence citation** — every arbitration decision cites gathered
  evidence, and cited values match the world's actual values;
  `decide()` raises on empty evidence.
- **Not a vote** — the higher-confidence proposal loses; flipping all
  confidences changes nothing.
- **AgentTrace** — suite lands under one trace ID, chain verifies,
  decision records present with evidence, timeline renders from the
  store alone, byte-identical across runs.

## Limitations

- **The agents are stubs.** Deterministic rule-based personas over
  scripted views, not LLM agents. That is deliberate — conflicts fire
  from evidence state, not model mood, so the demo is reproducible —
  but it means the system demonstrates the *coordination and
  arbitration layer*, not agent intelligence.
- **The decision rules are hand-written per conflict class.** A new
  conflict class needs a new evidence plan and a new rule. The
  mechanism (detect → gather new evidence → decide from evidence →
  cite it, or escalate) generalizes; the rules do not, yet.
- **"A2A-style" is honest shorthand, not a spec claim.** Task cards,
  agent cards, and lifecycle states are modeled on the A2A protocol's
  core concepts; this is not a wire-compatible A2A implementation.
- **The world is simulated.** Service state, deploys, and budgets are
  seeded fixtures. The arbiter's queries are real function calls
  against that state, but no real infrastructure is touched.
- **Escalation is terminal here.** In the tie scenario the run stops
  at "escalated to a human" — there is no human in the demo loop to
  resolve it and resume.
- **Execution is a state patch, not blast-radius.** Actions apply
  their scripted effects to the simulated world directly; wiring
  execution through the portfolio's checkpoint/rollback executor is
  composition work, not part of this repo.

## Where this sits

One line of layer distinction: factory-floor-agent is a single agent
that *acts*; MissionControl *coordinates actors who disagree*. In the
portfolio platform it is the second workload — a fleet whose conflicts
produce auditable decision records in the same AgentTrace store as
every other agent's work.
