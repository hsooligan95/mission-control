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
