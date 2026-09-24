#!/usr/bin/env python3
"""Find duplicated code and classify it: identical vs diverged. Stdlib only.

Two detectors:

* ``python`` (AST):
    IDENTICAL  - equal bodies after renaming parameters/locals; merging is
                 behaviour-preserving (still check imports and shadowing)
    SAME-NAME  - one name defined in >= 2 modules with different bodies.
                 Either a drifted copy of one concept (merging CHANGES
                 behaviour -> needs a decision) or an unrelated name clash
                 (rename). Text similarity cannot tell which: read each pair.
                 Bands (near-copy/partial/low) only order the reading;
                 "low" is NOT "unrelated".
* ``clone`` (any language): repeated blocks of >= --window normalised lines
  (whitespace collapsed, blank and comment-only lines dropped).

    python3 find_duplicates.py <root> [--mode python|clone|all] [--window 8]
                               [--show-diff] [--include-tests] [--json out.json]
"""
from __future__ import annotations

import argparse
import ast
import copy
import difflib
import hashlib
import json
import re
import sys
import warnings
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from measure import DEFAULT_EXCLUDES, TEST_PATH, iter_files, looks_generated  # noqa: E402

COMMON_NAMES = {
    "main", "run", "setup", "teardown", "as_dict", "to_dict", "from_dict", "to_json", "from_json",
    "__init__", "__repr__", "__str__", "__eq__", "__hash__", "__call__", "__enter__", "__exit__",
    "get", "set", "update", "close", "open", "start", "stop", "reset", "load", "save", "render",
    "validate", "parse", "handle", "process", "execute", "apply", "build", "create", "delete",
}
COMMENT_ONLY = re.compile(r"^(#|//|/\*|\*|\*/|--|<!--|;)")


def load_sources(root: Path, excludes: set[str], include_tests: bool):
    for path, rel in iter_files(root, excludes):
        text = path.read_bytes().decode("utf-8-sig", errors="replace").replace("\r\n", "\n")
        lines = text.splitlines()
        if looks_generated(rel, lines):
            continue
        if not include_tests and TEST_PATH.search(rel.as_posix()):
            continue
        yield rel, text, lines


def _strip_docstring(body):
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
            and isinstance(body[0].value.value, str):
        return body[1:]
    return body


class _AlphaRename(ast.NodeTransformer):
    """Rename parameters and locals by first appearance so renamed copies compare equal."""

    def __init__(self, names):
        self.map = {}
        self.names = names

    def _name(self, old):
        if old not in self.names:
            return old
        return self.map.setdefault(old, f"_v{len(self.map)}")

    def visit_Name(self, node):
        node.id = self._name(node.id)
        return node

    def visit_arg(self, node):
        node.arg = self._name(node.arg)
        return node


def _alpha_dump(fn, body) -> str:
    names = {a.arg for a in ast.walk(fn.args) if isinstance(a, ast.arg)}
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
    clone = copy.deepcopy(ast.Module(body=[ast.FunctionDef(
        name="f", args=fn.args, body=body, decorator_list=[], returns=None, type_params=[])], type_ignores=[]))
    return ast.dump(_AlphaRename(names).visit(clone))


def band(ratio: float) -> str:
    # Deliberately non-committal: a rewritten copy of one concept can score
    # very low, so "low" never means "safe to ignore".
    return "near-copy" if ratio >= 0.8 else "partial" if ratio >= 0.3 else "low"


def python_report(sources, min_chars: int, show_diff: bool, ignore: set[str]):
    by_body = defaultdict(list)
    by_name = defaultdict(list)
    for rel, text, _lines in sources:
        if rel.suffix != ".py":
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body = _strip_docstring(node.body)
            if not body:
                continue
            module = ast.Module(body=body, type_ignores=[])
            src = ast.unparse(module)
            try:
                dump = _alpha_dump(node, body)
            except TypeError:
                dump = ast.dump(module)
            loc = {"where": f"{rel}:{node.lineno}", "name": node.name, "module": str(rel),
                   "lines": node.end_lineno - node.lineno + 1, "src": src}
            if len(dump) >= min_chars:
                by_body[hashlib.sha1(dump.encode()).hexdigest()].append(loc)
            if node.name not in ignore:
                by_name[node.name].append((dump, loc))

    identical = [sorted(v, key=lambda x: x["where"]) for v in by_body.values() if len(v) > 1]
    identical.sort(key=lambda g: (-g[0]["lines"] * len(g), g[0]["where"]))

    diverged, collisions = [], []
    for name, defs in by_name.items():
        if len({loc["module"] for _d, loc in defs}) < 2:
            continue
        base_dump, base = defs[0]
        for dump, other in defs[1:]:
            if other["module"] == base["module"] or dump == base_dump:
                continue
            ratio = difflib.SequenceMatcher(None, base["src"], other["src"]).ratio()
            item = {"name": name, "a": base["where"], "b": other["where"], "similarity": round(ratio, 2),
                    "lines": max(base["lines"], other["lines"]), "same_body": base["src"] == other["src"]}
            if True:
                if show_diff:
                    item["diff"] = "\n".join(difflib.unified_diff(
                        base["src"].splitlines(), other["src"].splitlines(),
                        base["where"], other["where"], lineterm="", n=1))
                diverged.append(item)
    collisions = []
    for group in identical:
        for loc in group:
            loc.pop("src", None)
    same_name = sorted(diverged + collisions, key=lambda d: (not d["same_body"], -d["similarity"], d["name"]))
    for d in same_name:
        d["band"] = "same-body" if d["same_body"] else band(d["similarity"])
    return {"identical": identical, "same_name": same_name}


def clone_report(sources, window: int, min_chars: int, max_occurrences: int):
    files = []
    for rel, _text, lines in sources:
        norm = []
        for number, line in enumerate(lines, start=1):
            stripped = " ".join(line.split())
            if stripped and not COMMENT_ONLY.match(stripped):
                norm.append((number, stripped))
        if len(norm) >= window:
            files.append((rel, norm))

    index = defaultdict(list)
    for fi, (_rel, norm) in enumerate(files):
        for i in range(len(norm) - window + 1):
            chunk = [text for _n, text in norm[i:i + window]]
            if sum(map(len, chunk)) < min_chars or len(set(chunk)) < max(3, window // 2):
                continue
            index[hash("\n".join(chunk))].append((fi, i))

    seen, blocks = set(), []
    for occ in index.values():
        if len(occ) < 2 or len(occ) > max_occurrences:
            continue
        for a_idx in range(len(occ)):
            for b_idx in range(a_idx + 1, len(occ)):
                (fa, ia), (fb, ib) = occ[a_idx], occ[b_idx]
                if (fa, ia, fb, ib) in seen or (fa == fb and abs(ia - ib) < window):
                    continue
                na, nb = files[fa][1], files[fb][1]
                while ia > 0 and ib > 0 and na[ia - 1][1] == nb[ib - 1][1]:
                    ia, ib = ia - 1, ib - 1
                length = 0
                while ia + length < len(na) and ib + length < len(nb) and na[ia + length][1] == nb[ib + length][1]:
                    seen.add((fa, ia + length, fb, ib + length))
                    length += 1
                if length >= window:
                    blocks.append({
                        "lines": length,
                        "a": f"{files[fa][0]}:{na[ia][0]}-{na[ia + length - 1][0]}",
                        "b": f"{files[fb][0]}:{nb[ib][0]}-{nb[ib + length - 1][0]}",
                    })
    blocks.sort(key=lambda b: (-b["lines"], b["a"]))
    return {"blocks": blocks, "duplicated_lines": sum(b["lines"] for b in blocks)}


def main(argv=None):
    warnings.filterwarnings("ignore", category=SyntaxWarning)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--mode", choices=["python", "clone", "all"], default="all")
    ap.add_argument("--window", type=int, default=8, help="clone mode: minimum block size in lines")
    ap.add_argument("--min-chars", type=int, default=300, help="python mode: minimum AST size for identical bodies")
    ap.add_argument("--max-occurrences", type=int, default=25, help="clone mode: ignore boilerplate repeated more often")
    ap.add_argument("--ignore-names", nargs="*", default=[], help="extra function names to skip in same-name check")
    ap.add_argument("--include-tests", action="store_true")
    ap.add_argument("--show-diff", action="store_true")
    ap.add_argument("--exclude", nargs="*", default=[])
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--json")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    sources = list(load_sources(root, DEFAULT_EXCLUDES | set(args.exclude), args.include_tests))
    result = {"root": str(root)}
    t = args.top

    if args.mode in {"python", "all"} and any(rel.suffix == ".py" for rel, _t, _l in sources):
        py = python_report(sources, args.min_chars, args.show_diff, COMMON_NAMES | set(args.ignore_names))
        result["python"] = py
        print(f"== IDENTICAL function bodies (safe to merge): {len(py['identical'])} groups")
        for group in py["identical"][:t]:
            shown = "  ==  ".join(f"{g['where']} {g['name']}" for g in group[:4])
            more = f"  (+{len(group) - 4} more)" if len(group) > 4 else ""
            print(f"  [{group[0]['lines']} lines x{len(group)}] {shown}{more}")
        rows = py["same_name"]
        print(f"\n== SAME-NAME, different bodies: {len(rows)} pairs -- read each: drifted copy (decide) or clash (rename)"
              + (f"; showing {t}, full list via --json" if len(rows) > t else ""))
        for d in rows[:t]:
            print(f"  {d['band']:<10} sim={d['similarity']:<5} {d['name']}  {d['a']}  vs  {d['b']}")
            if d.get("diff"):
                print("    " + d["diff"].replace("\n", "\n    "))

    if args.mode in {"clone", "all"}:
        cl = clone_report(sources, args.window, 200, args.max_occurrences)
        result["clone"] = cl
        print(f"\n== CLONED blocks >= {args.window} lines (any language): {len(cl['blocks'])} blocks, "
              f"{cl['duplicated_lines']:,} duplicated lines")
        for b in cl["blocks"][:t]:
            print(f"  [{b['lines']:>4}] {b['a']}  ==  {b['b']}")

    if args.json:
        Path(args.json).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
