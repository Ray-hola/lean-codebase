# refactor-baseline

An agent skill for **behaviour-preserving codebase cleanup**, for any language and any size. It freezes a baseline first (tests, external interfaces, metrics). It then classifies every finding by whether fixing it preserves behaviour, and makes changes in small steps, each verified against that baseline.

The rule at its centre: **identical duplicates are safe to merge; diverged duplicates are not.** When two copies of one concept have drifted apart, merging them is a product decision, so it is surfaced to a human instead of being shipped as "dedupe".

The workflow draws on Nous Research's [Refactoring Hermes with 1,393 agents](https://nousresearch.com/refactoring-hermes-with-1393-agents) (frozen baseline, byte-for-byte interface checks, commit after every verified step). It adds the identical-vs-diverged split, batching by who must decide, and a list of regressions to catch.

## What's inside

| Path | Purpose |
|---|---|
| `SKILL.md` | The workflow: orient → freeze → find → batch → execute and verify → report |
| `scripts/measure.py` | LOC by language, size tier, big files, long functions, routing chains, CRLF/BOM hygiene. For Python: private cross-module imports, function-level imports, import cycles. Skips generated and minified files. |
| `scripts/find_duplicates.py` | Python: IDENTICAL bodies (after renaming parameters and locals) and SAME-NAME pairs with diffs. All languages: cloned blocks. |
| `scripts/snapshot.py` | Records command outputs (stdout, stderr, exit code) and compares them byte for byte, with masks for volatile text |
| `references/pitfalls.md` | 16 regressions that passed test suites, and how to catch each one |
| `references/project-types.md` | What to freeze for a library, CLI, service, frontend, data/ML, agent tooling, monorepo or infra project, plus static checks per language |
| `references/baseline-template.md` | A baseline document to fill in |

The scripts use only the Python 3.9+ standard library; there are no dependencies. They have been checked on a 26k-line Python project, a 190k-line TypeScript app and a 2.7M-line mixed Python/TypeScript monorepo (about 40 s per script).

## Install

Copy or clone the folder into your agent's skills directory:

```bash
git clone git@github.com:Ray-hola/refactor-baseline.git ~/.claude/skills/refactor-baseline   # Claude Code
# other runtimes: ~/.agents/skills/, ~/.codex/skills/, ~/.cursor/skills/, ...
```

The scripts also work on their own:

```bash
python3 scripts/measure.py /path/to/repo --json before.json
python3 scripts/find_duplicates.py /path/to/repo --show-diff
python3 scripts/snapshot.py record  --commands probes.txt
python3 scripts/snapshot.py compare --commands probes.txt
```

---

## 中文说明

一个用于**"行为不变"代码清理**的 Agent Skill，适用于各种语言、各种规模的项目。流程是：先冻结基线（测试、对外接口、度量）；再把每个问题按"修复后行为是否保持不变"分类；最后小步修改，每一步都对照基线验证后再提交。

核心规则：**逐字相同的重复可以放心合并；已经分叉的重复不能直接合并。** 同一概念的两份副本如果已经不一致，合并就等于替部分调用方改变了行为。这属于产品决策，必须交给人来拍板，不能当作"去重"顺手做掉。

- `SKILL.md`：完整流程。先摸清项目规则，然后冻结基线、找问题、分批（机械改动 / 需人决策 / 结构拆分）、逐步执行并验证，最后汇报。
- `scripts/`：三个只依赖标准库的脚本，分别做度量、重复检测（区分相同与分叉）、接口快照比对。
- `references/`：常见回归清单、按项目类型列出的应冻结接口、基线文档模板。

安装：把本目录复制到所用 Agent 的 skills 目录，例如 `~/.claude/skills/refactor-baseline`。

## License

MIT
