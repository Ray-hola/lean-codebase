# Contributing to refactor-baseline

Thanks for your interest in improving this skill. It stays deliberately small and dependency-free, so a few conventions keep it that way.

## Ground rules

- **Standard library only.** The three scripts and the tests must run on a clean Python 3.9+ with no `pip install`. If you reach for a third-party package, that is a sign the feature belongs elsewhere.
- **Python 3.9 is the floor.** Avoid `match` statements, `X | Y` type unions in annotations that are evaluated, and other 3.10+ syntax. CI runs 3.9–3.13; if it passes there, you are fine.
- **The scripts produce leads, not verdicts.** Keep that framing. `find_duplicates.py` must never label a diverged pair as "safe to merge", and `band()` must never call a low-similarity pair "unrelated". If you change classification wording, update `SKILL.md` and `references/pitfalls.md` to match.
- **This skill practices what it preaches.** A behaviour change to a script needs a test that pins the old and new behaviour. Do not "clean up" output formats without updating the tests that assert on them.

## Development

Run the test suite from the repo root:

```bash
python3 -m unittest discover -s tests -t . -b -v
```

Smoke-run the scripts on any real repo to sanity-check output:

```bash
python3 scripts/measure.py /path/to/repo
python3 scripts/find_duplicates.py /path/to/repo --show-diff
```

Optional static checks (not required, but nice):

```bash
python3 -m pyflakes scripts tests   # or: uvx pyflakes scripts tests
python3 -m compileall -q scripts tests
```

## Adding a test

Tests live in [`tests/test_scripts.py`](tests/test_scripts.py) and follow one pattern: build a small fixture tree in a temp dir, run a script's `main(argv)` with `--json`, and assert on the structured output (not the printed text). This keeps tests stable when wording changes. Add a case for every new detector or metric.

## Pull requests

- One logical change per PR. Keep the diff readable.
- Describe what you changed, how you verified it (test output), and any behaviour that changed.
- New detectors or metrics should come with: a test, a line in the relevant `--help`, and a mention in `SKILL.md` if an agent should know about them.

## Reporting bugs

Open an issue with the command you ran, the output you got, and what you expected. A minimal repository or file that reproduces the problem helps a lot — the scripts are deterministic, so a fixture usually pins the bug immediately.
