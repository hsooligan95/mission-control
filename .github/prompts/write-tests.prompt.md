---
mode: agent
description: Write tests for a named module in mission-control
---

Write tests for the module I name, following this repo's existing test
style, layout, and fixtures. Cover the behavior the module documents,
including these invariants where they apply:

- The arbiter's decide() receives ONLY the conflict and the evidence log — proposal confidences are never in scope; do not widen that signature.
- decide() raises on an empty evidence log: an uncited decision must be unproducible, and every decision cites the queries and values that decided it.
- Escalation is a valid outcome: when evidence doesn't discriminate, the arbiter escalates and nothing executes.

Then run the test suite:

    python -m pytest

Show the result. Do not claim done unless the suite is green; if a
test cannot pass, say why instead of weakening the assertion.
