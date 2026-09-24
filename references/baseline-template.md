# Code cleanup baseline (<YYYY-MM-DD>)

This document is a frozen snapshot taken before cleanup: metrics, findings, completed steps and open decisions. Compare every later batch against it. The numbers are as of the date above. To re-measure, run the commands in §6.

- Base commit: `<sha>` (`<branch>`)
- Work branch: `<branch>`
- Project rules that constrain the cleanup: <e.g. "no big-bang refactor", public API policy>

## 1. Baseline metrics

| Metric | Baseline | Latest |
|---|---|---|
| Tests | <N passed / M failed (pre-existing: …)> | |
| Source LOC (size tier) | | |
| Files > 1000 lines | | |
| Functions > 150 lines | | |
| Longest routing chain | | |
| Private cross-module imports | | |
| Import cycles | | |
| Line-ending / BOM issues | | |

## 2. Frozen interfaces

- `probes.txt`: <count> probes (<what: --help ×N, schema dump, public names…>)
- Treated as public even with no in-repo callers: <list>

## 3. Findings

### 3.1 Diverged duplicates: merging changes behaviour, needs a decision

| Concept | Variant A | Variant B | Difference | Affected callers | Recommendation |
|---|---|---|---|---|---|

### 3.2 Structural issues

- <misplaced helpers / cycles / god files / divergent entry points / config resolution…>

### 3.3 Identical duplicates: safe to merge

- <list, or "see find_duplicates output">

## 4. Done

| Commit | Change | Verification |
|---|---|---|

Regressions caught before commit:
- <…>

## 5. Next

- **Batch 0 (mechanical):** …
- **Batch 1 (decisions):** one line per row of §3.1.
- **Batch 2 (structural):** …

## 6. Re-measure

```bash
<test command>
python3 <skill>/scripts/measure.py . --json .refactor-baseline/metrics-after.json
python3 <skill>/scripts/find_duplicates.py . --show-diff
python3 <skill>/scripts/snapshot.py compare --commands probes.txt
```
