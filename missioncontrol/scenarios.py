"""The scenario set: 3 conflict classes + 1 control.

Per the Idea Critic's minimum credible evidence set, each conflict
scenario passed an ambiguity screen before it was admitted: the
``losing_defense`` field is the one-paragraph case for the proposal
that loses -- written from the evidence available to its proposer at
decision time. If that paragraph could not be written convincingly,
the scenario would be rigged, and it would not be here.

Each scenario carries: the world's ground truth, each agent's partial
view (what that persona plausibly saw -- possibly stale), the scripted
effects of executing an action, and the checks the verify agent runs.
"""
from __future__ import annotations

SCENARIOS = [
    {
        "id": "rollback-vs-scale",
        "title": "checkout-api error spike: rollback vs scale",
        "class": "action conflict (deploy regression vs capacity)",
        "incident": "checkout-api 5xx rate at 31%, p95 latency 2.4s, "
                    "request queue backing up.",
        "world": {
            "services": {
                "checkout-api": {"status": "degraded", "replicas": 3,
                                 "version": "v2.4.1", "error_rate": 0.31,
                                 "queue_depth": 1840, "p95_ms": 2400},
            },
            "deploys": [{"service": "checkout-api", "version": "v2.4.1",
                         "minutes_ago": 12,
                         "note": "payment client retry-policy change"}],
            "error_onset": {"checkout-api": {"minutes_ago": 11}},
            "dependencies": {"checkout-api": {"payment-gw": "healthy",
                                              "inventory-db": "healthy"}},
            "error_budgets": {"checkout-api": {"remaining_pct": 18.0,
                                               "burn_samples": [6.2]}},
            "clusters": {},
        },
        "views": {
            "diagnose": {
                "target": "checkout-api", "propose_action": "scale",
                "confidence": 0.8,
                "claims": {"queue_cause": "capacity saturation"},
                "basis": "queue depth 1840 and climbing, p95 2.4s across "
                         "all replicas -- reads as saturation",
            },
            "triage": {
                "target": "checkout-api", "propose_action": "rollback",
                "confidence": 0.6,
                "claims": {"spike_cause": "code regression"},
                "basis": "runbook RB-114: error spike shortly after a "
                         "deploy means roll back first, investigate after",
            },
        },
        "effects": {
            "rollback": {"services": {"checkout-api": {
                "version": "v2.4.0", "error_rate": 0.01,
                "queue_depth": 40, "p95_ms": 210, "status": "healthy"}}},
            "scale": {"services": {"checkout-api": {
                "replicas": 6, "queue_depth": 1500}}},
        },
        "checks": [
            {"service": "checkout-api", "field": "error_rate",
             "op": "<=", "value": 0.02},
            {"service": "checkout-api", "field": "queue_depth",
             "op": "<=", "value": 100},
        ],
        "losing_defense": "Scaling was defensible: the queue and latency "
                          "signals diagnose saw are the textbook signature "
                          "of saturation, its snapshot predated the deploy "
                          "notice, and adding replicas is the reversible, "
                          "low-risk first move in most queue incidents. It "
                          "loses only because the live evidence -- deploy "
                          "12 min ago, errors starting 1 min later, every "
                          "dependency healthy -- ties the spike to the new "
                          "code, where more replicas just retry faster.",
    },
    {
        "id": "restart-vs-failover",
        "title": "orders-db: restart the replica vs fail over",
        "class": "world-state conflict (contradictory claims about the primary)",
        "incident": "orders-db replication alerts firing; one probe "
                    "reports the primary unreachable.",
        "world": {
            "services": {
                "orders-db-primary": {"status": "healthy",
                                      "accepting_writes": True,
                                      "connections": 212},
                "orders-db-replica": {"status": "lagging",
                                      "replica_lag_s": 340},
            },
            "deploys": [],
            "error_onset": {},
            "dependencies": {},
            "error_budgets": {},
            "clusters": {"orders-db": {"primary_status": "healthy",
                                       "replica_lag_s": 340,
                                       "lag_trend": "decreasing"}},
        },
        "views": {
            "diagnose": {
                "target": "orders-db", "propose_action": "failover",
                "confidence": 0.7,
                "claims": {"orders-db.primary_status": "down"},
                "basis": "health probe to the primary timed out twice; "
                         "replication alerts firing -- reads as a dead "
                         "primary",
            },
            "remediate": {
                "target": "orders-db", "propose_action": "restart-replica",
                "confidence": 0.65,
                "claims": {"orders-db.primary_status": "healthy"},
                "basis": "write traffic is still landing on the primary; "
                         "the replica fell behind during the bulk import "
                         "and its applier thread looks wedged",
            },
        },
        "effects": {
            "restart-replica": {"services": {"orders-db-replica": {
                "status": "healthy", "replica_lag_s": 2}},
                "clusters": {"orders-db": {"replica_lag_s": 2}}},
            "failover": {"services": {"orders-db-primary": {
                "status": "demoted", "accepting_writes": False}}},
        },
        "checks": [
            {"service": "orders-db-replica", "field": "replica_lag_s",
             "op": "<=", "value": 10},
            {"service": "orders-db-primary", "field": "accepting_writes",
             "op": "==", "value": True},
        ],
        "losing_defense": "Failover was defensible: two consecutive probe "
                          "timeouts plus replication alerts are exactly "
                          "what a dead primary looks like from the outside, "
                          "and every minute spent doubting it in a real "
                          "outage is downtime. It loses only because the "
                          "live query shows the primary healthy and "
                          "accepting writes -- the probe path was stale -- "
                          "and the replica it would promote is 340s "
                          "behind, so failing over would have lost "
                          "committed orders.",
    },
    {
        "id": "page-vs-wait",
        "title": "search-api error budget burn: page vs wait",
        "class": "genuine tie (evidence does not discriminate) -> escalation",
        "incident": "search-api error budget burning at an unsteady "
                    "rate; 4% of the monthly budget remains.",
        "world": {
            "services": {
                "search-api": {"status": "degraded", "replicas": 4,
                               "version": "v1.9.3", "error_rate": 0.04,
                               "queue_depth": 120, "p95_ms": 640},
            },
            "deploys": [{"service": "search-api", "version": "v1.9.3",
                         "minutes_ago": 1560,
                         "note": "index schema refresh (yesterday)"}],
            "error_onset": {"search-api": {"minutes_ago": 95}},
            "dependencies": {"search-api": {"ranking-svc": "flapping",
                                            "index-store": "healthy"}},
            "error_budgets": {"search-api": {
                "remaining_pct": 4.0,
                "burn_samples": [1.8, 0.7, 2.1, 0.9]}},
            "clusters": {},
        },
        "views": {
            "triage": {
                "target": "search-api", "propose_action": "page",
                "confidence": 0.55,
                "claims": {"budget_view": "critical"},
                "basis": "only 4% of the error budget remains; runbook "
                         "says page the secondary and freeze deploys "
                         "before it is gone",
            },
            "diagnose": {
                "target": "search-api", "propose_action": "wait",
                "confidence": 0.5,
                "claims": {"burn_view": "transient"},
                "basis": "burn rate oscillates around the threshold and "
                         "one dependency is flapping -- reads as "
                         "external and self-limiting",
            },
        },
        "effects": {},
        "checks": [],
        "losing_defense": "Neither proposal loses -- that is the point of "
                          "this scenario. Paging is defensible (4% budget "
                          "left is genuinely critical) and waiting is "
                          "defensible (the burn oscillates and tracks a "
                          "flapping dependency). The arbiter's gathered "
                          "evidence lands in the ambiguous band, so the "
                          "correct system behavior is to escalate to a "
                          "human with both cases and the evidence, not "
                          "to manufacture a winner.",
    },
    {
        "id": "control-agreement",
        "title": "worker-pool hung worker: agents agree (control)",
        "class": "control (agreement -- arbitration must NOT fire)",
        "incident": "worker-7 in the job worker pool has a hung "
                    "process; its queue is backing up slowly.",
        "world": {
            "services": {
                "worker-7": {"status": "hung", "queue_depth": 96,
                             "error_rate": 0.0},
            },
            "deploys": [], "error_onset": {}, "dependencies": {},
            "error_budgets": {}, "clusters": {},
        },
        "views": {
            "triage": {
                "target": "worker-7", "propose_action": "restart",
                "confidence": 0.9,
                "claims": {"worker-7.process": "hung"},
                "basis": "runbook RB-032: hung stateless worker -> "
                         "restart in place",
            },
            "diagnose": {
                "target": "worker-7", "propose_action": "restart",
                "confidence": 0.85,
                "claims": {"worker-7.process": "hung"},
                "basis": "process alive but not consuming; heartbeat "
                         "stale 14 min; no in-flight state to lose",
            },
        },
        "effects": {
            "restart": {"services": {"worker-7": {
                "status": "healthy", "queue_depth": 3}}},
        },
        "checks": [
            {"service": "worker-7", "field": "queue_depth",
             "op": "<=", "value": 10},
        ],
        "losing_defense": "There is no losing proposal: both agents, from "
                          "independent signals, propose the same action "
                          "with consistent claims. The control exists to "
                          "prove the conflict detector stays silent when "
                          "it should -- an arbiter that fires on agreement "
                          "is overhead, not governance.",
    },
]
