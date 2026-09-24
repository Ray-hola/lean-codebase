# Regressions that cleanup introduces, and how to catch them

Every item here slipped past a passing test suite in a real cleanup.

| # | Pitfall | How it happens | How to catch it |
|---|---|---|---|
| 1 | **Shadowed import** | You rename a helper to `foo` and import it, but the caller already has a local variable `foo`. In Python that raises `UnboundLocalError` only when that path runs. | Before picking a new name, grep the target file for `\bfoo\b`. Choose a name that doesn't collide. |
| 2 | **Missing import after redirect** | A call moves from `a._helper()` to `b.helper()`, but the file never imported `b`. | Run a static undefined-name check (`pyflakes`, `tsc --noEmit`, compile) after every step, not only at the end. |
| 3 | **Deleted "unused" public name** | Nothing in the repo calls it, but plugins, downstream packages or users do. | Treat exported symbols, documented names and names referenced only by tests as public. Snapshot the public surface (`dir(pkg)`, `.d.ts`, `go doc`). |
| 4 | **Mass-rewritten error handling** | An automated rewrite such as `try/except/pass` → `suppress()` changes which exceptions get swallowed at dozens of sites. | Never batch-rewrite exception handling. Migrate site by site, and compare the caught exception types at each one. |
| 5 | **Diverged copies merged as "dedupe"** | Two "duplicates" differ in one filter or one default, and merging picks one. | `find_duplicates.py` SAME-NAME with `--show-diff`. Treat any non-identical pair as a decision. |
| 6 | **Vacuous A/B** | The old and new outputs match only because both runs were refused early (auth, privacy or feature flag). | Assert that the probe reached the changed code: check for expected output markers, or a non-refusal exit code on at least one case. |
| 7 | **Untested path** | Tests pass because nothing exercises the branch you changed. | Grep tests for the entry point. If it's missing, write a throwaway A/B probe (SKILL.md, Phase 4 step 6). |
| 8 | **Line endings / BOM** | Mixed CRLF/LF makes exact-match edit tools fail, or makes diffs unreadable. | Normalise in a separate whitespace-only commit and check `git diff -w --ignore-cr-at-eol` shows (almost) nothing. Add `.gitattributes`. |
| 9 | **Stale baseline files** | The snapshot directory still holds files from an earlier run, so the diff flags "changes" you never made. | Use a dedicated directory per run and check file timestamps before comparing. |
| 10 | **Dispatch-table conversion changes semantics** | An `if/elif` chain relied on order, fall-through, overlapping conditions or side effects inside the conditions. | Convert only chains of pure equality checks on one key. Keep the default branch. Snapshot every command's `--help` and a golden run. |
| 11 | **Moved code breaks monkeypatch targets** | Tests patch `module.attr`, and after the move the patch hits a name nobody reads any more, so the test still passes but tests nothing. | Grep tests for `setattr(`, `patch("pkg.mod.name"` and `mocker.patch` strings naming anything you move. |
| 12 | **New import cycle** | Moving a helper into a "neutral" module that imports back from its callers. | After each move, run an import smoke test of every module, e.g. `python -c "import pkg.a, pkg.b, ..."`. Rerun `measure.py` and check the cycle count doesn't go up. |
| 13 | **Metric gaming** | A lines-of-code target drives deleting comments and docstrings, or inlining. Line count falls while readability doesn't improve. | Track long functions, cycles, duplicates and private imports, not just LOC. Never delete comments or docstrings to hit a number. |
| 14 | **Splits that raise coupling** | A god file becomes 20 modules that all import each other, and startup gets slower. | Compare the cycle count and function-level import count before and after. Time imports of the main entry points. |
| 15 | **Parallel workers collide** | Two workers both edit a shared registry or `__init__`. | Split the work into non-overlapping areas. Give each shared file one owner; everyone else sends that owner the change. |
| 16 | **Generated code counted** | Bundles, `*.gen.*` and protobuf outputs inflate metrics or get "refactored". | `measure.py` lists skipped files. Check that list, and never edit generated files; change the generator instead. |
