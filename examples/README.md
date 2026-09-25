# Worked example

A 30-second, end-to-end run of the three scripts on a tiny **synthetic** project.

> Everything under [`sample_project/`](sample_project/) is invented toy code
> written only for this demo — no real codebase is used or shown. It contains a
> handful of problems planted on purpose so the scripts have something to find.

## The planted problems

| File(s) | Problem | What the skill calls it |
|---|---|---|
| `orders.py`, `invoices.py` | `calc_order_total` and `sum_line_items` are the same body with different parameter/local names | **Identical** → safe to merge |
| `subscriptions.py`, `legacy_subs.py` | Two `is_active` functions that quietly disagree (one also excludes expired subs) | **Diverged** → human decision |
| `events.py` | An 8-branch `if/elif` chain on one key | Routing chain → dispatch-table candidate |
| `config.py`, `settings.py` | Import each other | 2-cycle → misplaced helper |

## 1. Measure the baseline

```bash
python3 ../../scripts/measure.py .
```

```
source LOC: 96   test LOC: 0   size tier: small
  python       files=7      source=96        test=0
files > 1000 lines: 0
functions > 150 lines: 0
routing chains >= 8 branches: 1
        8  events.py:9 (if/elif chain)
skipped as generated/minified: 0 files, 0 lines
line endings: crlf=0 mixed=0 bom=0
python private cross-module imports: 0
python function-level imports: 0  two-cycles: 1
  config <-> settings
```

It found the routing chain and the import cycle — both structural leads to look at, not verdicts.

## 2. Find duplicates — and classify them

```bash
python3 ../../scripts/find_duplicates.py . --show-diff
```

```
== IDENTICAL function bodies (safe to merge): 1 groups
  [8 lines x2] invoices.py:4 sum_line_items  ==  orders.py:4 calc_order_total

== SAME-NAME, different bodies: 1 pairs -- read each: drifted copy (decide) or clash (rename)
  partial    sim=0.68  is_active  legacy_subs.py:9  vs  subscriptions.py:4
    --- legacy_subs.py:9
    +++ subscriptions.py:4
    @@ -1 +1 @@
    -return sub.status == 'active' and (not sub.is_expired())
    +return sub.status == 'active'

== CLONED blocks >= 8 lines (any language): 0 blocks, 0 duplicated lines
```

This is the heart of the skill:

- **`calc_order_total` / `sum_line_items` are IDENTICAL** even though every name
  differs. Merging them into one shared helper preserves behaviour — a Batch 0
  mechanical change (still grep for shadowing and missing imports first).
- **The two `is_active` functions are NOT.** One excludes expired subscriptions;
  the other doesn't. Merging them picks a winner and silently changes behaviour
  for the callers of the loser. The tool refuses to call this "safe" — it's a
  **Batch 1 decision** for a human: which definition is correct, and which
  callers change? Note the similarity band says `partial`, not "unrelated" — a
  low score never means safe to ignore.

## 3. Freeze the interface, then prove a change is safe

Record a baseline of externally visible behaviour (public names + golden runs):

```bash
python3 ../../scripts/snapshot.py record  --commands probes.txt --dir .refactor-baseline/snapshots
python3 ../../scripts/snapshot.py compare --commands probes.txt --dir .refactor-baseline/snapshots
```

```
recorded 3 probes -> .refactor-baseline/snapshots
compared 3 probes: 0 changed, 0 without baseline
```

Now suppose someone "cleans up" `subscriptions.is_active` and changes its
behaviour. `compare` catches it byte-for-byte and exits non-zero:

```
--- baseline/golden_is_active
+++ current/golden_is_active
@@ -1,5 +1,5 @@
 [exit 0]
 --- stdout
-True False
+False True
 --- stderr
compared 3 probes: 1 changed, 0 without baseline
```

Any diff means stop: revert the step, or reclassify it as a decision.

## How this maps to the workflow

| Finding | Batch | Who decides |
|---|---|---|
| Merge the identical `calc_*` bodies | 0 (mechanical) | Agent |
| Convert the `events.py` chain to a dispatch table (equality on one key, keep the default) | 0 (mechanical) | Agent |
| Move the shared helper to break the `config ↔ settings` cycle | 0 (mechanical) | Agent |
| Reconcile the two `is_active` definitions | 1 (decision) | **Human** |

## Reproduce it

From this directory:

```bash
python3 ../../scripts/measure.py .
python3 ../../scripts/find_duplicates.py . --show-diff
python3 ../../scripts/snapshot.py record  --commands probes.txt
python3 ../../scripts/snapshot.py compare --commands probes.txt
```

The scripts are deterministic, so your output matches what's shown above.
