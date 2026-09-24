#!/usr/bin/env python3
"""Freeze externally visible behaviour and compare it byte for byte. Stdlib only.

Each non-empty, non-# line of the commands file is one probe:

    name<TAB>shell command        (or just: shell command -> name derived)

Examples of probes worth freezing: every CLI ``--help``, an OpenAPI/JSON-schema
dump, a route listing, ``python -c "import pkg; print(sorted(dir(pkg)))"``
(public names), a golden-input run of a pure function, ``npm run build`` output
file hashes.

    python3 snapshot.py record  --commands probes.txt --dir .refactor-baseline/snapshots
    python3 snapshot.py compare --commands probes.txt --dir .refactor-baseline/snapshots
            [--mask REGEX ...]   # e.g. timestamps, temp paths, durations

``compare`` exits 1 and prints a unified diff for every probe that changed.
stdout, stderr and the exit code are all part of the snapshot.
"""
from __future__ import annotations

import argparse
import difflib
import re
import subprocess
import sys
from pathlib import Path


def probes(path: Path):
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _, cmd = line.partition("\t")
        if not cmd:
            cmd = name
            name = re.sub(r"[^A-Za-z0-9_.-]+", "_", cmd).strip("_")[:120] or "probe"
        yield name, cmd


def capture(cmd: str, cwd: str | None, timeout: int, masks) -> str:
    try:
        done = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True,
                              timeout=timeout, errors="replace")
        text = f"$ {cmd}\n[exit {done.returncode}]\n--- stdout\n{done.stdout}--- stderr\n{done.stderr}"
    except subprocess.TimeoutExpired:
        text = f"$ {cmd}\n[timeout after {timeout}s]\n"
    for pattern in masks:
        text = re.sub(pattern, "<MASKED>", text)
    return text


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["record", "compare"])
    ap.add_argument("--commands", required=True)
    ap.add_argument("--dir", default=".refactor-baseline/snapshots")
    ap.add_argument("--cwd")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--mask", nargs="*", default=[], help="regexes replaced by <MASKED> before storing/comparing")
    args = ap.parse_args(argv)
    out = Path(args.dir)
    out.mkdir(parents=True, exist_ok=True)
    items = list(probes(Path(args.commands)))
    names = [n for n, _ in items]
    if len(set(names)) != len(names):
        sys.exit("duplicate probe names; give them explicit names with a TAB")

    changed, missing = [], []
    for name, cmd in items:
        current = capture(cmd, args.cwd, args.timeout, args.mask)
        target = out / f"{name}.snap"
        if args.action == "record":
            target.write_text(current, encoding="utf-8")
            continue
        if not target.is_file():
            missing.append(name)
            continue
        before = target.read_text(encoding="utf-8")
        if before != current:
            changed.append(name)
            sys.stdout.writelines(difflib.unified_diff(
                before.splitlines(True), current.splitlines(True), f"baseline/{name}", f"current/{name}"))
    if args.action == "record":
        print(f"recorded {len(items)} probes -> {out}")
        return 0
    print(f"compared {len(items)} probes: {len(changed)} changed, {len(missing)} without baseline")
    for name in missing:
        print(f"  no baseline: {name}")
    return 1 if changed or missing else 0


if __name__ == "__main__":
    sys.exit(main())
