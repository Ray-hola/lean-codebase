# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project aims
to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `SKILL.md` Phase 0.5 "Kickoff contract": an upfront, one-question-at-a-time
  interview (adapted from the `grill-me` skill) that fixes the operating
  contract — scope, public-API policy, Batch 0 autonomy, discovered-decision
  handling, red lines, reporting — so execution then runs unattended within it.
  Recorded in a new §0 of `references/baseline-template.md`.
- Stdlib `unittest` test suite (`tests/`) covering `measure.py`,
  `find_duplicates.py` and `snapshot.py`.
- GitHub Actions CI running the suite on Python 3.9–3.13 and smoke-running the
  scripts on this repo.
- `CONTRIBUTING.md`, issue and pull-request templates, and README badges.
- `examples/`: a worked run of all three scripts on a synthetic toy project,
  with real captured output.
- README: a "Why this approach" section (philosophy + advantages) and a
  "Credits & source" section citing the Nous Research article, in English and
  Chinese.

## [0.1.0] - 2026-09-25

### Added
- Initial `refactor-baseline` skill: freeze → classify → change workflow in
  `SKILL.md`, with the core rule that identical duplicates are safe to merge
  and diverged duplicates need a human decision.
- `scripts/measure.py`: LOC by language, size tier, big files, long functions,
  routing chains, line-ending/BOM hygiene, and Python import coupling.
- `scripts/find_duplicates.py`: identical-vs-diverged duplicate detection for
  Python plus cross-language clone detection.
- `scripts/snapshot.py`: byte-for-byte interface snapshots with masking.
- References: `pitfalls.md`, `project-types.md`, `baseline-template.md`.

[Unreleased]: https://github.com/Ray-hola/refactor-baseline/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Ray-hola/refactor-baseline/releases/tag/v0.1.0
