#!/usr/bin/env python3
"""Measure a codebase before/after cleanup. Stdlib only, any language.

Reports: LOC per language (source vs test), size tier, big files, long
functions, if/elif routing chains, line-ending/BOM hygiene, and for Python
packages: cross-module private imports, function-level imports, 2-cycles.

    python3 measure.py <root> [--json out.json] [--big-file 1000] [--long-func 150]
                              [--exclude DIR ...] [--top 15]

Function lengths are exact for Python (AST) and approximate for brace
languages (signature regex + brace depth). Treat approximate numbers as
trend indicators, not exact counts.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path

LANG = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".go": "go", ".java": "java", ".kt": "kotlin",
    ".rs": "rust", ".c": "c", ".h": "c", ".cc": "cpp", ".cpp": "cpp", ".hpp": "cpp", ".cs": "csharp",
    ".swift": "swift", ".php": "php", ".rb": "ruby", ".scala": "scala", ".dart": "dart",
    ".vue": "vue", ".svelte": "svelte", ".lua": "lua", ".sh": "shell", ".sql": "sql",
}
BRACE_LANGS = {"javascript", "typescript", "go", "java", "kotlin", "rust", "c", "cpp", "csharp",
               "swift", "php", "scala", "dart"}
DEFAULT_EXCLUDES = {".git", "node_modules", ".venv", "venv", "env", "__pycache__", "dist", "build",
                    "target", "vendor", ".next", ".nuxt", "out", "coverage", ".tox", ".mypy_cache",
                    ".pytest_cache", ".idea", ".vscode", "third_party", "site-packages", "Pods"}
TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|spec|specs|testing)(/|$)|(^|/)test_[^/]+$|_test\.\w+$|\.(test|spec)\.\w+$")
FUNC_SIG = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?"
    r"(?:(?:public|private|protected|internal|static|final|override|virtual|abstract|inline|suspend)\s+)*"
    r"(?:func\s+(?:\([^)]*\)\s*)?(\w+)|fn\s+(\w+)|function\s*\*?\s*(\w+)|fun\s+(\w+)|def\s+(\w+)"
    r"|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>"
    r"|[\w<>\[\],\s\*&:]+?\s+(\w+)\s*\([^;]*\)\s*(?:const\s*)?(?:throws\s+[\w.,\s]+)?\s*\{?\s*$)"
)
GENERATED_NAME = re.compile(r"(\.min\.|\.gen\.|\.generated\.|_pb2\.py$|\.pb\.go$|bundle\.[cm]?js$|\.d\.ts$)", re.I)
GENERATED_MARK = re.compile(r"@generated|do not edit", re.I)
BRACE_CAP = 5000
NOT_FUNC = {"if", "for", "while", "switch", "catch", "return", "else", "new", "sizeof", "do", "try"}


def iter_files(root: Path, excludes: set[str]):
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in excludes or (part.startswith(".") and part not in {".", ".."} and part != ".github")
               for part in rel.parts[:-1]):
            continue
        if path.is_file() and path.suffix.lower() in LANG:
            yield path, rel


def looks_generated(rel: Path, lines: list[str]) -> bool:
    if GENERATED_NAME.search(rel.name):
        return True
    if any(GENERATED_MARK.search(line) for line in lines[:8]):
        return True
    sample = lines[:200]
    return bool(sample) and sum(len(x) for x in sample) / len(sample) > 500


def py_functions(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def elif_chain(node: ast.If) -> int:
    n = 1
    while len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
        node, n = node.orelse[0], n + 1
    return n


def brace_functions(lines: list[str]):
    """Approximate (name, start, length, else_if_count) for brace languages.

    Functions whose braces never balance within BRACE_CAP lines are dropped:
    that means the heuristic lost track (regex/template literals), not that
    the function is huge.
    """
    out, i = [], 0
    while i < len(lines):
        m = FUNC_SIG.match(lines[i])
        name = next((g for g in m.groups() if g), None) if m else None
        if not name or name in NOT_FUNC:
            i += 1
            continue
        depth, started, j = 0, False, i
        while j < len(lines) and j < i + BRACE_CAP:
            code = re.sub(r"(\"(\\.|[^\"\\])*\"|'(\\.|[^'\\])*'|`[^`]*`|//.*$)", "", lines[j])
            depth += code.count("{") - code.count("}")
            started = started or "{" in code
            if started and depth <= 0:
                break
            if not started and j > i + 3:
                break
            j += 1
        if started and depth <= 0:
            body = lines[i:j + 1]
            out.append((name, i + 1, j - i + 1, sum(len(re.findall(r"\belse\s+if\b", x)) for x in body)))
        i += 1
    return out


def main(argv=None):
    warnings.filterwarnings("ignore", category=SyntaxWarning)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--json", help="write full metrics to this file")
    ap.add_argument("--big-file", type=int, default=1000)
    ap.add_argument("--long-func", type=int, default=150)
    ap.add_argument("--exclude", nargs="*", default=[])
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    excludes = DEFAULT_EXCLUDES | set(args.exclude)

    loc = defaultdict(lambda: {"source": 0, "test": 0, "files": 0})
    big, long_funcs, routing, hygiene = [], [], [], {"crlf": [], "mixed": [], "bom": []}
    generated = []
    py_modules: dict[str, Path] = {}
    py_trees = {}
    for path, rel in iter_files(root, excludes):
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            hygiene["bom"].append(str(rel))
        crlf = raw.count(b"\r\n")
        lf = raw.count(b"\n") - crlf
        if crlf and lf:
            hygiene["mixed"].append(str(rel))
        elif crlf:
            hygiene["crlf"].append(str(rel))
        text = raw.decode("utf-8-sig", errors="replace").replace("\r\n", "\n")
        lines = text.splitlines()
        lang = LANG[path.suffix.lower()]
        if looks_generated(rel, lines):
            generated.append((len(lines), str(rel)))
            continue
        kind = "test" if TEST_PATH.search(rel.as_posix()) else "source"
        loc[lang][kind] += len(lines)
        loc[lang]["files"] += 1
        if kind == "test":
            continue
        if len(lines) > args.big_file:
            big.append((len(lines), str(rel)))
        if lang == "python":
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            py_trees[rel] = tree
            py_modules[".".join(rel.with_suffix("").parts)] = rel
            for fn in py_functions(tree):
                n = fn.end_lineno - fn.lineno + 1
                if n > args.long_func:
                    long_funcs.append((n, f"{rel}:{fn.lineno} {fn.name}", "exact"))
                ifs = sum(isinstance(s, ast.If) for s in fn.body)
                if ifs >= 8:
                    routing.append((ifs, f"{rel}:{fn.lineno} {fn.name} (sequential if)"))
            for node in ast.walk(tree):
                if isinstance(node, ast.If):
                    c = elif_chain(node)
                    if c >= 8:
                        routing.append((c, f"{rel}:{node.lineno} (if/elif chain)"))
        elif lang in BRACE_LANGS:
            for name, start, n, elifs in brace_functions(lines):
                if n > args.long_func:
                    long_funcs.append((n, f"{rel}:{start} {name}", "approx"))
                if elifs + 1 >= 8:
                    routing.append((elifs + 1, f"{rel}:{start} {name} (if/else-if, approx)"))

    # Python package coupling: resolve imports against modules found under root.
    private, lazy, edges = Counter(), Counter(), set()
    short = defaultdict(set)
    for dotted in py_modules:
        parts = dotted.split(".")
        for k in range(1, len(parts) + 1):
            short[".".join(parts[-k:])].add(dotted)

    def resolve(name):
        hits = short.get(name) or set()
        return next(iter(hits)) if len(hits) == 1 else None

    for rel, tree in py_trees.items():
        me = ".".join(rel.with_suffix("").parts)
        top = {id(n) for n in tree.body}
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            targets = []
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                mod = resolve(node.module)
                if mod:
                    targets.append(mod)
                    for alias in node.names:
                        sub = resolve(f"{node.module}.{alias.name}")
                        if sub:
                            targets.append(sub)
                        elif alias.name.startswith("_") and not alias.name.startswith("__"):
                            private[f"{mod}.{alias.name}"] += 1
            elif isinstance(node, ast.Import):
                targets += [m for m in (resolve(a.name) for a in node.names) if m]
            for t in targets:
                if t != me:
                    edges.add((me, t))
                    if id(node) not in top:
                        lazy[me] += 1
    cycles = sorted({tuple(sorted(e)) for e in edges if (e[1], e[0]) in edges})

    source_loc = sum(v["source"] for v in loc.values())
    tier = ("small" if source_loc < 10_000 else "medium" if source_loc < 100_000
            else "large" if source_loc < 1_000_000 else "huge")
    result = {
        "root": str(root),
        "source_loc": source_loc,
        "test_loc": sum(v["test"] for v in loc.values()),
        "size_tier": tier,
        "loc_by_language": dict(sorted(loc.items(), key=lambda kv: -kv[1]["source"])),
        "big_files": sorted(big, reverse=True),
        "long_functions": sorted(long_funcs, reverse=True),
        "routing_chains": sorted(routing, reverse=True),
        "hygiene": hygiene,
        "skipped_generated": sorted(generated, reverse=True),
        "python_coupling": {
            "private_cross_module_imports": sum(private.values()),
            "private_imports_top": private.most_common(args.top),
            "function_level_imports": sum(lazy.values()),
            "function_level_imports_by_module": lazy.most_common(args.top),
            "two_cycles": cycles,
        } if py_trees else None,
    }
    if args.json:
        Path(args.json).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    t = args.top
    print(f"root: {root}")
    print(f"source LOC: {source_loc:,}   test LOC: {result['test_loc']:,}   size tier: {tier}")
    for lang, v in list(result["loc_by_language"].items())[:8]:
        print(f"  {lang:12} files={v['files']:<6} source={v['source']:<9,} test={v['test']:,}")
    print(f"files > {args.big_file} lines: {len(big)}")
    for n, f in result["big_files"][:t]:
        print(f"  {n:7,}  {f}")
    print(f"functions > {args.long_func} lines: {len(long_funcs)}")
    for n, f, how in result["long_functions"][:t]:
        print(f"  {n:7,}  {f}{'' if how == 'exact' else '  (approx)'}")
    print(f"routing chains >= 8 branches: {len(routing)}")
    for n, f in result["routing_chains"][:t]:
        print(f"  {n:7}  {f}")
    print(f"skipped as generated/minified: {len(generated)} files, {sum(n for n, _ in generated):,} lines")
    for n, f in result["skipped_generated"][:min(t, 5)]:
        print(f"  {n:7,}  {f}")
    print(f"line endings: crlf={len(hygiene['crlf'])} mixed={len(hygiene['mixed'])} bom={len(hygiene['bom'])}")
    if py_trees:
        pc = result["python_coupling"]
        print(f"python private cross-module imports: {pc['private_cross_module_imports']}")
        for name, c in pc["private_imports_top"][:t]:
            print(f"  x{c:<4} {name}")
        print(f"python function-level imports: {pc['function_level_imports']}  two-cycles: {len(cycles)}")
        for a, b in cycles[:t]:
            print(f"  {a} <-> {b}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
