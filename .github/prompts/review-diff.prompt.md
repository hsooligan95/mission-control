---
mode: agent
description: Review the current diff against mission-control's invariants
---

Review my current diff against this repo's invariants:

- The arbiter's decide() receives ONLY the conflict and the evidence log — proposal confidences are never in scope; do not widen that signature.
- decide() raises on an empty evidence log: an uncited decision must be unproducible, and every decision cites the queries and values that decided it.
- Escalation is a valid outcome: when evidence doesn't discriminate, the arbiter escalates and nothing executes.
- A new scenario class needs a written losing_defense in scenarios.py, and the control case must show zero arbiter queries.

Flag every violation with file and line. Also flag any change that
alters a documented behavior contract (output shapes, exit codes,
event schemas, recorded artifacts) without updating the docs and
tests that describe it. No style nitpicks — correctness and contract
violations only.
