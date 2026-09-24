---
name: Feature request
about: Suggest a new metric, detector, or workflow improvement
title: ""
labels: enhancement
assignees: ""
---

**What problem does this solve**
What cleanup mistake would it catch, or what would it make easier?

**Proposed change**
Which script or reference, and roughly how it would behave.

**Constraints to keep in mind**
- Standard library only (Python 3.9+, no `pip install`).
- The scripts produce leads, not verdicts — a detector must not mark a diverged
  duplicate as "safe to merge".

**Alternatives considered**
