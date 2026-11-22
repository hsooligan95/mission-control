# MissionControl — suite run report

Trace ID: `trace-missioncontrol-7` · 44 events in the AgentTrace store · chain verified by the renderer below.

## rollback-vs-scale — checkout-api error spike: rollback vs scale

*action conflict (deploy regression vs capacity)*

Incident: checkout-api 5xx rate at 31%, p95 latency 2.4s, request queue backing up.

- **diagnose** proposes **scale** (confidence 0.8): queue depth 1840 and climbing, p95 2.4s across all replicas -- reads as saturation
- **triage** proposes **rollback** (confidence 0.6): runbook RB-114: error spike shortly after a deploy means roll back first, investigate after

**Arbiter decision record:**

```json
{
  "decision_point": "mission-control.arbitration",
  "decider": "arbiter",
  "computed": true,
  "conflict": {
    "class": "action",
    "key": null,
    "parties": [
      "diagnose",
      "triage"
    ],
    "actions": [
      "scale",
      "rollback"
    ]
  },
  "choice": "rollback",
  "options": [
    "scale",
    "rollback"
  ],
  "evidence": {
    "queries": [
      {
        "tool": "deploy_recency",
        "args": {
          "service": "checkout-api"
        },
        "result": {
          "service": "checkout-api",
          "version": "v2.4.1",
          "minutes_ago": 12,
          "note": "payment client retry-policy change"
        }
      },
      {
        "tool": "error_onset",
        "args": {
          "service": "checkout-api"
        },
        "result": {
          "minutes_ago": 11
        }
      },
      {
        "tool": "dependency_health",
        "args": {
          "service": "checkout-api"
        },
        "result": {
          "payment-gw": "healthy",
          "inventory-db": "healthy"
        }
      }
    ],
    "reasons": [
      "deploy v2.4.1 landed 12 min ago; errors began 11 min ago (1 min after the deploy)",
      "all dependencies healthy ({'payment-gw': 'healthy', 'inventory-db': 'healthy'}), so the errors are not explained by a downstream outage",
      "queue depth is a symptom of retrying failed requests, not a capacity shortfall: scaling would amplify retries against broken code"
    ]
  }
}
```

Outcome: **resolved**

## restart-vs-failover — orders-db: restart the replica vs fail over

*world-state conflict (contradictory claims about the primary)*

Incident: orders-db replication alerts firing; one probe reports the primary unreachable.

- **diagnose** proposes **failover** (confidence 0.7): health probe to the primary timed out twice; replication alerts firing -- reads as a dead primary
- **remediate** proposes **restart-replica** (confidence 0.65): write traffic is still landing on the primary; the replica fell behind during the bulk import and its applier thread looks wedged

**Arbiter decision record:**

```json
{
  "decision_point": "mission-control.arbitration",
  "decider": "arbiter",
  "computed": true,
  "conflict": {
    "class": "world-state",
    "key": "orders-db.primary_status",
    "parties": [
      "diagnose",
      "remediate"
    ],
    "actions": [
      "failover",
      "restart-replica"
    ]
  },
  "choice": "restart-replica",
  "options": [
    "failover",
    "restart-replica"
  ],
  "evidence": {
    "queries": [
      {
        "tool": "service_state",
        "args": {
          "service": "orders-db-primary"
        },
        "result": {
          "status": "healthy",
          "accepting_writes": true,
          "connections": 212
        }
      },
      {
        "tool": "replica_state",
        "args": {
          "cluster": "orders-db"
        },
        "result": {
          "primary_status": "healthy",
          "replica_lag_s": 340,
          "lag_trend": "decreasing"
        }
      }
    ],
    "reasons": [
      "live query: primary status is 'healthy' (accepting_writes=True) -- the 'primary down' claim came from a stale probe",
      "replica lag is 340s and decreasing: failing over would promote a stale replica and lose committed writes",
      "restarting the replica clears the lag without touching the healthy primary"
    ]
  }
}
```

Outcome: **resolved**

## page-vs-wait — search-api error budget burn: page vs wait

*genuine tie (evidence does not discriminate) -> escalation*

Incident: search-api error budget burning at an unsteady rate; 4% of the monthly budget remains.

- **triage** proposes **page** (confidence 0.55): only 4% of the error budget remains; runbook says page the secondary and freeze deploys before it is gone
- **diagnose** proposes **wait** (confidence 0.5): burn rate oscillates around the threshold and one dependency is flapping -- reads as external and self-limiting

**Arbiter decision record:**

```json
{
  "decision_point": "mission-control.arbitration",
  "decider": "arbiter",
  "computed": true,
  "conflict": {
    "class": "action",
    "key": null,
    "parties": [
      "triage",
      "diagnose"
    ],
    "actions": [
      "page",
      "wait"
    ]
  },
  "choice": "ESCALATE",
  "options": [
    "page",
    "wait"
  ],
  "evidence": {
    "queries": [
      {
        "tool": "error_budget",
        "args": {
          "service": "search-api"
        },
        "result": {
          "remaining_pct": 4.0,
          "burn_samples": [
            1.8,
            0.7,
            2.1,
            0.9
          ]
        }
      },
      {
        "tool": "deploy_recency",
        "args": {
          "service": "search-api"
        },
        "result": {
          "service": "search-api",
          "version": "v1.9.3",
          "minutes_ago": 1560,
          "note": "index schema refresh (yesterday)"
        }
      },
      {
        "tool": "dependency_health",
        "args": {
          "service": "search-api"
        },
        "result": {
          "ranking-svc": "flapping",
          "index-store": "healthy"
        }
      }
    ],
    "reasons": [
      "burn samples [1.8, 0.7, 2.1, 0.9] average 1.38x -- inside the ambiguous band (0.8-1.5x), neither clearly paging nor clearly transient",
      "error budget remaining is 4.0%, and one dependency is flapping intermittently, so the burn may be external",
      "the gathered evidence does not discriminate between the two proposals; escalating to a human with both proposals and this evidence attached"
    ]
  }
}
```

Outcome: **escalated**

## control-agreement — worker-pool hung worker: agents agree (control)

*control (agreement -- arbitration must NOT fire)*

Incident: worker-7 in the job worker pool has a hung process; its queue is backing up slowly.

- **triage** proposes **restart** (confidence 0.9): runbook RB-032: hung stateless worker -> restart in place
- **diagnose** proposes **restart** (confidence 0.85): process alive but not consuming; heartbeat stale 14 min; no in-flight state to lose
Outcome: **resolved**

## Timeline (rendered from the AgentTrace store)

# MissionControl — suite run in the AgentTrace store

Trace ID(s): `trace-missioncontrol-7` · 44 events · sources: mission-control
**Chain OK — 44 events, every hash verified.**

```
trace-missioncontrol-7
├── mission-control (44 events)
│   #  1 2026-11-21T16:30:00Z  suite_started      
│   #  2 2026-11-21T16:31:00Z  run_started        
│   #  3 2026-11-21T16:32:00Z  task_card          
│   #  4 2026-11-21T16:33:00Z  proposal           
│   #  5 2026-11-21T16:34:00Z  task_card          
│   #  6 2026-11-21T16:35:00Z  proposal           
│   #  7 2026-11-21T16:36:00Z  handoff            
│   #  8 2026-11-21T16:37:00Z  conflict_detected  
│   #  9 2026-11-21T16:38:00Z  arbitration        DECISION mission-control.arbitration: rollback (decider=arbiter, computed=True)
│   # 10 2026-11-21T16:39:00Z  action_executed    
│   # 11 2026-11-21T16:40:00Z  verification       
│   # 12 2026-11-21T16:41:00Z  run_completed      
│   # 13 2026-11-21T16:42:00Z  run_started        
│   # 14 2026-11-21T16:43:00Z  task_card          
│   # 15 2026-11-21T16:44:00Z  proposal           
│   # 16 2026-11-21T16:45:00Z  task_card          
│   # 17 2026-11-21T16:46:00Z  proposal           
│   # 18 2026-11-21T16:47:00Z  handoff            
│   # 19 2026-11-21T16:48:00Z  conflict_detected  
│   # 20 2026-11-21T16:49:00Z  arbitration        DECISION mission-control.arbitration: restart-replica (decider=arbiter, computed=True)
│   # 21 2026-11-21T16:50:00Z  action_executed    
│   # 22 2026-11-21T16:51:00Z  verification       
│   # 23 2026-11-21T16:52:00Z  run_completed      
│   # 24 2026-11-21T16:53:00Z  run_started        
│   # 25 2026-11-21T16:54:00Z  task_card          
│   # 26 2026-11-21T16:55:00Z  proposal           
│   # 27 2026-11-21T16:56:00Z  task_card          
│   # 28 2026-11-21T16:57:00Z  proposal           
│   # 29 2026-11-21T16:58:00Z  handoff            
│   # 30 2026-11-21T16:59:00Z  conflict_detected  
│   # 31 2026-11-21T17:00:00Z  arbitration        DECISION mission-control.arbitration: ESCALATE (decider=arbiter, computed=True)
│   # 32 2026-11-21T17:01:00Z  escalated          
│   # 33 2026-11-21T17:02:00Z  run_completed      
│   # 34 2026-11-21T17:03:00Z  run_started        
│   # 35 2026-11-21T17:04:00Z  task_card          
│   # 36 2026-11-21T17:05:00Z  proposal           
│   # 37 2026-11-21T17:06:00Z  task_card          
│   # 38 2026-11-21T17:07:00Z  proposal           
│   # 39 2026-11-21T17:08:00Z  handoff            
│   # 40 2026-11-21T17:09:00Z  agreement          
│   # 41 2026-11-21T17:10:00Z  action_executed    
│   # 42 2026-11-21T17:11:00Z  verification       
│   # 43 2026-11-21T17:12:00Z  run_completed      
│   # 44 2026-11-21T17:13:00Z  suite_verdict      DECISION mission-control.suite_verdict: 3/4 incidents resolved, 1 escalated, 3 arbitrated (decider=mission-control, computed=True)
```

## Decision records (computed decision points only)

- #9 **mission-control.arbitration** -> **rollback**
  - deploy v2.4.1 landed 12 min ago; errors began 11 min ago (1 min after the deploy)
  - all dependencies healthy ({'payment-gw': 'healthy', 'inventory-db': 'healthy'}), so the errors are not explained by a downstream outage
  - queue depth is a symptom of retrying failed requests, not a capacity shortfall: scaling would amplify retries against broken code
- #20 **mission-control.arbitration** -> **restart-replica**
  - live query: primary status is 'healthy' (accepting_writes=True) -- the 'primary down' claim came from a stale probe
  - replica lag is 340s and decreasing: failing over would promote a stale replica and lose committed writes
  - restarting the replica clears the lag without touching the healthy primary
- #31 **mission-control.arbitration** -> **ESCALATE**
  - burn samples [1.8, 0.7, 2.1, 0.9] average 1.38x -- inside the ambiguous band (0.8-1.5x), neither clearly paging nor clearly transient
  - error budget remaining is 4.0%, and one dependency is flapping intermittently, so the burn may be external
  - the gathered evidence does not discriminate between the two proposals; escalating to a human with both proposals and this evidence attached
- #44 **mission-control.suite_verdict** -> **3/4 incidents resolved, 1 escalated, 3 arbitrated**
  - rollback-vs-scale: resolved (chose rollback)
  - restart-vs-failover: resolved (chose restart-replica)
  - page-vs-wait: escalated (chose ESCALATE)
  - control-agreement: resolved (chose agreed action)

## Timeline (store order)

- #  1 `2026-11-21T16:30:00Z` **mission-control** — suite_started — 
- #  2 `2026-11-21T16:31:00Z` **mission-control** — run_started — 
- #  3 `2026-11-21T16:32:00Z` **mission-control** — task_card — 
- #  4 `2026-11-21T16:33:00Z` **mission-control** — proposal — 
- #  5 `2026-11-21T16:34:00Z` **mission-control** — task_card — 
- #  6 `2026-11-21T16:35:00Z` **mission-control** — proposal — 
- #  7 `2026-11-21T16:36:00Z` **mission-control** — handoff — 
- #  8 `2026-11-21T16:37:00Z` **mission-control** — conflict_detected — 
- #  9 `2026-11-21T16:38:00Z` **mission-control** — arbitration — DECISION mission-control.arbitration: rollback (decider=arbiter, computed=True)
- # 10 `2026-11-21T16:39:00Z` **mission-control** — action_executed — 
- # 11 `2026-11-21T16:40:00Z` **mission-control** — verification — 
- # 12 `2026-11-21T16:41:00Z` **mission-control** — run_completed — 
- # 13 `2026-11-21T16:42:00Z` **mission-control** — run_started — 
- # 14 `2026-11-21T16:43:00Z` **mission-control** — task_card — 
- # 15 `2026-11-21T16:44:00Z` **mission-control** — proposal — 
- # 16 `2026-11-21T16:45:00Z` **mission-control** — task_card — 
- # 17 `2026-11-21T16:46:00Z` **mission-control** — proposal — 
- # 18 `2026-11-21T16:47:00Z` **mission-control** — handoff — 
- # 19 `2026-11-21T16:48:00Z` **mission-control** — conflict_detected — 
- # 20 `2026-11-21T16:49:00Z` **mission-control** — arbitration — DECISION mission-control.arbitration: restart-replica (decider=arbiter, computed=True)
- # 21 `2026-11-21T16:50:00Z` **mission-control** — action_executed — 
- # 22 `2026-11-21T16:51:00Z` **mission-control** — verification — 
- # 23 `2026-11-21T16:52:00Z` **mission-control** — run_completed — 
- # 24 `2026-11-21T16:53:00Z` **mission-control** — run_started — 
- # 25 `2026-11-21T16:54:00Z` **mission-control** — task_card — 
- # 26 `2026-11-21T16:55:00Z` **mission-control** — proposal — 
- # 27 `2026-11-21T16:56:00Z` **mission-control** — task_card — 
- # 28 `2026-11-21T16:57:00Z` **mission-control** — proposal — 
- # 29 `2026-11-21T16:58:00Z` **mission-control** — handoff — 
- # 30 `2026-11-21T16:59:00Z` **mission-control** — conflict_detected — 
- # 31 `2026-11-21T17:00:00Z` **mission-control** — arbitration — DECISION mission-control.arbitration: ESCALATE (decider=arbiter, computed=True)
- # 32 `2026-11-21T17:01:00Z` **mission-control** — escalated — 
- # 33 `2026-11-21T17:02:00Z` **mission-control** — run_completed — 
- # 34 `2026-11-21T17:03:00Z` **mission-control** — run_started — 
- # 35 `2026-11-21T17:04:00Z` **mission-control** — task_card — 
- # 36 `2026-11-21T17:05:00Z` **mission-control** — proposal — 
- # 37 `2026-11-21T17:06:00Z` **mission-control** — task_card — 
- # 38 `2026-11-21T17:07:00Z` **mission-control** — proposal — 
- # 39 `2026-11-21T17:08:00Z` **mission-control** — handoff — 
- # 40 `2026-11-21T17:09:00Z` **mission-control** — agreement — 
- # 41 `2026-11-21T17:10:00Z` **mission-control** — action_executed — 
- # 42 `2026-11-21T17:11:00Z` **mission-control** — verification — 
- # 43 `2026-11-21T17:12:00Z` **mission-control** — run_completed — 
- # 44 `2026-11-21T17:13:00Z` **mission-control** — suite_verdict — DECISION mission-control.suite_verdict: 3/4 incidents resolved, 1 escalated, 3 arbitrated (decider=mission-control, computed=True)
