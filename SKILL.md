---
name: refactor-baseline
description: Use when asked to clean up, simplify, deduplicate or refactor a codebase, audit it for duplicated or tangled logic, shrink god files or long functions, or set a baseline before code optimization. Applies to any language and any size, from a single package to a large monorepo.
---

# Refactor Baseline

## Overview

Cleanup goes wrong in two ways. Either behaviour changes without anyone noticing, or a behaviour decision gets made under the label "dedupe". This skill prevents both:

1. **Freeze** tests, external interfaces and metrics before touching code.
2. **Classify** every finding by whether fixing it preserves behaviour.
3. **Change** in small, verified, committed steps, each checked against the frozen baseline.

Before all three, a short **kickoff** (Phase 0.5) settles the operating contract with the human once — scope, autonomy, red lines — so the rest of the run can proceed unattended instead of stopping for permission at every step.

**Core rule: identical duplicates are safe to merge; diverged duplicates are not.** When two copies of one concept have drifted apart, merging them picks a winner and silently changes behaviour for the callers of the loser. That is a product decision, so present it to the human; never ship it as cleanup.

Don't use this skill for feature work or a single bug fix.

## Tools (stdlib Python 3.9+, no install)

| Script | Purpose |
|---|---|
| `scripts/measure.py <root> [--json f]` | LOC by language, size tier, big files, long functions, routing chains, CRLF/BOM hygiene. For Python it also reports private cross-module imports, function-level imports and import cycles. Generated and minified files are skipped and listed separately. |
| `scripts/find_duplicates.py <root> [--show-diff] [--json f]` | Python: IDENTICAL bodies (after renaming parameters and locals) and SAME-NAME pairs with diffs. All languages: cloned blocks. |
| `scripts/snapshot.py record\|compare --commands probes.txt` | Freezes command output (stdout, stderr and exit code) and diffs it byte for byte. |

Numbers from brace languages (JS/TS/Go/Java/…) are marked `approx`; use them to rank work, not as exact counts. Run a script with `--help` for its full options.

## Phase 0: Orient

- Read the project's rules first: `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING`, lint config. Rules such as "no big-bang refactor", public-API policy or protected directories override anything in this skill.
- Check `git status`. Never touch untracked or modified files that belong to the user.
- Work on a new branch. For parallel workers (large repos), give each one its own `git worktree`.
- Keep baseline artifacts under `.refactor-baseline/` in the repo or in a temp dir, and don't commit them unless asked. Before comparing, check that the directory holds only this run's files, because stale snapshots from earlier runs cause false diffs.

## Phase 0.5: Kickoff contract

Move every judgement call the human owns to the *front*, so the run itself can proceed unattended. Interview the human once, agree the rules, write them down, then execute against them without asking permission at every step. (The interview mechanics — one question at a time, each with a recommended answer to react to — are adapted from the [grill-me](https://github.com/satya-janghu/agent-skills) skill.)

- **Investigate before asking.** Anything the repo answers — the public-API surface, protected dirs in `CLAUDE.md`/`CONTRIBUTING`, the test command, `git status` — you already read in Phase 0. Don't ask it.
- **One question at a time, with a recommended default.** Give the human something to react to, not a blank form. Most will take the defaults; the questions exist to catch the cases where they wouldn't.
- **Decide rules, not findings.** This phase fixes *how* you work. It does **not** decide the diverged-duplicate verdicts — those don't exist yet; they surface in Phase 2 and are handled per the "discovered decisions" rule below. Don't let kickoff swell into a spec-everything waterfall.

Agree on and record in §0 of the baseline doc:

| Dimension | What to settle | Default |
|---|---|---|
| **Scope** | Directories/packages in scope; off-limits ones (vendored, generated, someone else's active work). | Whole repo minus generated/vendored. |
| **Public-API policy** | What counts as public (exported names, anything with external callers, plugin/registry entries), and whether renaming or removing a public name is ever on the table. | Nothing public changes without a decision. |
| **Batch 0 autonomy** | May the agent land mechanical changes (merge IDENTICAL copies, dispatch tables, cycle breaks, proven-dead private code) unattended, or does each need review? | Land unattended; commit per step. |
| **Discovered decisions** | When Phase 2 turns up a diverged duplicate or divergent entry point: stop and ask now, or queue it to Batch 1 and keep going? | Queue and continue; present all at the end. |
| **Red lines** | Max LOC per commit, files never to touch, "no big-bang" / one-file-per-step rules. | One coherent change per commit; no file-count-shrinking big bangs. |
| **Reporting** | Where and how often the human reviews. | Final report plus the Batch 1 decision list. |

The filled-in §0 is the mandate: within it the agent runs Phases 1–4 on its own, and comes back to the human only to step outside it or when it hits a red line.

## Phase 1: Freeze the baseline

1. **Tests.** Run the suite and record the pass/fail counts and runtime. If some tests already fail, record exactly which ones as pre-existing. When a failure appears later, rerun it on the untouched baseline before blaming your change.
2. **Interfaces.** Write `probes.txt` with every externally visible behaviour you must preserve (see `references/project-types.md`), then run `snapshot.py record`. Use `--mask` for timestamps, durations and temp paths.
3. **Metrics.** Run `measure.py <root> --json .refactor-baseline/metrics-before.json`.
4. **Baseline doc.** Fill in `references/baseline-template.md`: the metrics table, the frozen interfaces and the base commit. It becomes the reference that every later batch is compared against.

## Phase 2: Find problems

Run `find_duplicates.py --show-diff`, then **read the code**. The scripts produce leads; they don't make verdicts.

- **IDENTICAL groups**: candidates for a single shared definition. Tiny bodies repeated many times (a lazy-import `__getattr__`, a `register()` hook) are often a deliberate pattern. Decide case by case whether a shared helper really helps.
- **SAME-NAME pairs**: for each pair, decide whether it is a *drifted copy of one concept* (write down exactly what differs and which callers see which behaviour) or an *unrelated name clash* (a rename candidate). The bands `near-copy` / `partial` / `low` only set the reading order. **A rewritten copy can score `low`**, so read every pair of private helpers with the same name.
- **Same concept, different names**: search for the concept, not the name. Tokenizers, path/config resolution, "is this record active/current", retry/backoff, serialization and date parsing tend to exist 3–6 times under different names.
- **Divergent entry points**: find every place that calls the same core pipeline (for example CLI, web, API and eval harness all calling `answer()`), then compare the arguments, defaults, model or config choices and safety filters they pass. Divergence here is a behaviour difference users actually see.
- **Structure**: god files, long functions, long `if/elif` routing chains; *private cross-module imports*, which signal a helper living in the wrong module; import cycles and the function-level imports added to dodge them.
- **Hygiene**: mixed CRLF/LF and BOMs. Fix them before anything else, in a separate whitespace-only commit, because they also break exact-match editing tools.
- **Dead code**: grep for callers across source, tests, entry points, dynamic imports, plugin registries and docs. "Only referenced by tests" or "exported" means public: do not delete it without a decision.

## Phase 3: Batch the work

| Batch | Contents | Who decides |
|---|---|---|
| **0: mechanical** | Whitespace/BOM normalisation (own commit). Merging IDENTICAL copies. Extracting code repeated verbatim within one file. Moving misplaced helpers to a neutral module to break cycles. Replacing routing chains with dispatch tables that keep order and fall-through. Removing private code proven dead. | Agent, if the project rules allow it |
| **1: decisions** | Every drifted copy, every divergent entry point, every default that differs. For each, present: the variants, the concrete difference, who is affected, a recommended canonical version, and which tests or evals will change. | **Human** |
| **2: structural** | Splitting god files and long functions: one file or function per step. | Agent, with review |

Do batch 0 first: it shrinks the surface and makes the batch 1 diffs easier to read. Never mix batches in one commit.

## Phase 4: Execute; verify every step

For each step:

1. Make the smallest coherent change.
2. **Before renaming or adding an import**, grep the target file for the new name, because a local variable with that name will shadow the import.
3. Run a static check for undefined names and unused imports: `pyflakes`/`ruff`, `tsc --noEmit`, `go vet`, `cargo check`, or a compile.
4. Run the tests and compare against the Phase 1 counts.
5. Run `snapshot.py compare`. Any diff means stop: either revert, or reclassify the step into batch 1.
6. **If the path you touched has no test**, write a throwaway A/B probe. Run it on the old code (`git stash`) and on the new code, compare the outputs, then delete the probe. **Confirm the probe actually reached the changed code.** A guard that refuses both runs (for example a permission or privacy gate) makes old and new "identical" without proving anything.
7. Commit, stating in the message that behaviour is preserved and how you verified it.
8. Update the "done" table in the baseline doc.

**Stop and ask** when a test fails that isn't pre-existing and the fix isn't obvious, or a snapshot changes unexpectedly, or a step would cross a kickoff-contract red line. When a "mechanical" step turns out to need a behaviour choice, handle it per the contract's discovered-decisions rule: stop now, or reclassify it into batch 1 and continue.

The full list of regressions the checks above catch is in `references/pitfalls.md`. Read it before a large run.

## Scaling by size

Use the `size tier` reported by `measure.py`:

| Tier | Source LOC | Strategy |
|---|---|---|
| small | < 10k | One agent, sequential, one branch. The whole baseline takes minutes. |
| medium | 10k–100k | Sequential batches with one commit per step. Plan batch 0 across the whole repo. |
| large | 100k–1M | Split into **non-overlapping areas** (by directory or ownership). Give each worker its own worktree and a brief: the area, the interfaces to preserve, the required checks, and a rule to commit after every verified step. The orchestrator doesn't edit code; it integrates branches and reruns the full checks against the frozen baseline. Give shared files (registries, `__init__`, routing tables) a single owner. |
| huge | > 1M | Same as large, plus metrics per area, several review rounds, and an explicit check for removed public names. Share language servers or indexers between worktrees to avoid running one per worker. |

## Report

Lead with the outcome: which steps were done, the before/after metrics, and verification evidence (test counts and snapshot results). Then list what was caught and fixed before commit. End with the batch 1 decisions the human needs to make, each with its options and a recommendation. Don't claim "behaviour unchanged" for any step that lacks test, snapshot or A/B evidence.
