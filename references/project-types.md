# What to freeze, by project type

Put each probe on its own line in `probes.txt` for `scripts/snapshot.py`, written as `name<TAB>command`. Freeze everything that someone outside the refactored code can observe.

| Project type | Freeze (probes) | Also check |
|---|---|---|
| **Library / SDK** | The public surface: `python -c "import pkg, json; print(json.dumps(sorted(n for n in dir(pkg) if not n.startswith('_'))))"` for each public module, `tsc --declaration` output or `.d.ts`, `go doc -all ./...`. Serialized formats and error messages. | Semver: removing or renaming a public name is a breaking change. |
| **CLI** | Every `--help` (root and each subcommand), exit codes, golden runs on fixture inputs, config parsing output. | `--help` text that is byte-identical is a strong signal the argument wiring is intact. |
| **Web service / API** | OpenAPI or route table dump, responses to fixture requests (masking ids and times), status codes for error paths. | Leave DB migrations and schema untouched in cleanup batches. |
| **Frontend app** | `build` succeeds, the route list, type check, existing snapshot or Storybook tests. | Bundle size before and after. Visual screenshots are optional. |
| **Data / ML pipeline** | A golden run on a tiny fixture dataset, output hashes or metrics within a tolerance, fixed seeds. | Same row counts and schema at every stage. |
| **Agent / LLM tooling** | Tool JSON schemas, prompt texts, retrieval results for fixed queries, eval scores with an offline stub model. | Safety, privacy or permission gates behave the same on allowed and denied cases. Test both. |
| **Monorepo** | Per-package interfaces plus the list of cross-package imports. | Assign areas by package, and give shared config one owner. |
| **Scripts / infra** | Dry-run output, rendered configs (`terraform plan`, `helm template`, `kustomize build`). | No real apply or deploy during cleanup. |

## Static checks by language

| Language | Undefined names / compile | Lint (optional) |
|---|---|---|
| Python | `pyflakes` (or `uvx pyflakes`), `python -m compileall -q` | `ruff`, `mypy` |
| TypeScript / JS | `tsc --noEmit` | `eslint` |
| Go | `go build ./... && go vet ./...` | `staticcheck` |
| Rust | `cargo check` | `cargo clippy` |
| Java / Kotlin | `gradle compileJava` / `compileKotlin`, or `mvn -q compile` | — |
| C / C++ | Build with `-Wall -Werror` | `clang-tidy` |
