#!/usr/bin/env python3
"""Tests for the refactor-baseline scripts. Stdlib unittest only, no deps.

Run from the repo root:

    python3 -m unittest discover -s tests -t .

The scripts under scripts/ are stdlib-only, so these tests are too. Each test
builds a small fixture tree in a temp dir, runs a script's ``main(argv)`` (or a
pure function), and asserts on the structured ``--json`` output rather than the
printed text, so wording changes don't break the suite.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import measure  # noqa: E402
import find_duplicates  # noqa: E402
import snapshot  # noqa: E402


def write(root: Path, rel: str, text: str, *, crlf: bool = False, bom: bool = False) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.replace("\n", "\r\n") if crlf else text
    raw = data.encode("utf-8")
    if bom:
        raw = b"\xef\xbb\xbf" + raw
    path.write_bytes(raw)
    return path


class MeasureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def _run(self, *extra):
        out = self.root / "metrics.json"
        rc = measure.main([str(self.root), "--json", str(out), *extra])
        self.assertEqual(rc, 0)
        return json.loads(out.read_text(encoding="utf-8"))

    def test_loc_and_size_tier(self):
        write(self.root, "a.py", "x = 1\ny = 2\nz = 3\n")
        result = self._run()
        self.assertEqual(result["source_loc"], 3)
        self.assertEqual(result["size_tier"], "small")
        self.assertIn("python", result["loc_by_language"])

    def test_tests_counted_separately(self):
        write(self.root, "src.py", "a = 1\n")
        write(self.root, "test_src.py", "b = 2\nc = 3\n")
        result = self._run()
        self.assertEqual(result["source_loc"], 1)
        self.assertEqual(result["test_loc"], 2)

    def test_big_files_and_long_functions(self):
        write(self.root, "big.py", "".join(f"v{i} = {i}\n" for i in range(12)))
        body = "\n".join(f"    step_{i} = {i}" for i in range(10))
        write(self.root, "long.py", f"def worker():\n{body}\n    return step_0\n")
        result = self._run("--big-file", "5", "--long-func", "4")
        self.assertTrue(any("big.py" in f for _n, f in result["big_files"]))
        self.assertTrue(any("worker" in f for _n, f, _how in result["long_functions"]))

    def test_hygiene_crlf_and_bom(self):
        write(self.root, "dos.py", "a = 1\nb = 2\n", crlf=True)
        write(self.root, "bom.py", "c = 3\n", bom=True)
        result = self._run()
        self.assertIn("dos.py", result["hygiene"]["crlf"])
        self.assertIn("bom.py", result["hygiene"]["bom"])

    def test_generated_files_skipped(self):
        write(self.root, "hand.py", "a = 1\n")
        write(self.root, "thing.gen.py", "b = 2\n")
        result = self._run()
        self.assertTrue(any("thing.gen.py" in f for _n, f in result["skipped_generated"]))
        self.assertFalse(any("thing.gen.py" in f for f in [k for k in result["loc_by_language"]]))

    def test_import_cycle_detected(self):
        write(self.root, "alpha.py", "import beta\n\nx = 1\n")
        write(self.root, "beta.py", "import alpha\n\ny = 2\n")
        result = self._run()
        self.assertGreaterEqual(len(result["python_coupling"]["two_cycles"]), 1)


class FindDuplicatesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def _run(self, *extra):
        out = self.root / "dups.json"
        rc = find_duplicates.main([str(self.root), "--json", str(out), "--min-chars", "20", *extra])
        self.assertEqual(rc, 0)
        return json.loads(out.read_text(encoding="utf-8"))

    def test_identical_after_alpha_rename(self):
        # Same body, different parameter and local names -> one IDENTICAL group.
        write(self.root, "mod_a.py",
              "def compute_total(items):\n    total = 0\n    for item in items:\n"
              "        total += item\n    return total\n")
        write(self.root, "mod_b.py",
              "def compute_sum(values):\n    total = 0\n    for value in values:\n"
              "        total += value\n    return total\n")
        result = self._run()
        self.assertGreaterEqual(len(result["python"]["identical"]), 1)

    def test_same_name_diverged_pair(self):
        write(self.root, "one.py", "def resolve_path(p):\n    return p.strip().lower()\n")
        write(self.root, "two.py", "def resolve_path(p):\n    return p.upper() + '/'\n")
        result = self._run("--show-diff")
        names = [d["name"] for d in result["python"]["same_name"]]
        self.assertIn("resolve_path", names)
        pair = next(d for d in result["python"]["same_name"] if d["name"] == "resolve_path")
        self.assertFalse(pair["same_body"])
        self.assertIn("diff", pair)

    def test_common_names_ignored(self):
        write(self.root, "x.py", "def main():\n    return 1\n")
        write(self.root, "y.py", "def main():\n    return 2\n")
        result = self._run()
        self.assertNotIn("main", [d["name"] for d in result["python"]["same_name"]])

    def test_clone_block_detected(self):
        block = "".join(f"result_line_number_{i} = compute_something({i})\n" for i in range(6))
        write(self.root, "c1.py", f"def f():\n{block}    return result_line_number_0\n")
        write(self.root, "c2.py", f"def g():\n{block}    return result_line_number_0\n")
        report = find_duplicates.clone_report(
            list(find_duplicates.load_sources(self.root, measure.DEFAULT_EXCLUDES, False)),
            window=4, min_chars=50, max_occurrences=25)
        self.assertGreaterEqual(len(report["blocks"]), 1)

    def test_band_never_calls_low_safe(self):
        self.assertEqual(find_duplicates.band(0.9), "near-copy")
        self.assertEqual(find_duplicates.band(0.5), "partial")
        self.assertEqual(find_duplicates.band(0.1), "low")


class SnapshotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.snapdir = self.root / "snaps"

    def _probes(self, text: str) -> Path:
        p = self.root / "probes.txt"
        p.write_text(text, encoding="utf-8")
        return p

    def test_record_then_compare_identical(self):
        probes = self._probes("hello\techo hello\n")
        self.assertEqual(snapshot.main(["record", "--commands", str(probes), "--dir", str(self.snapdir)]), 0)
        self.assertTrue((self.snapdir / "hello.snap").is_file())
        self.assertEqual(snapshot.main(["compare", "--commands", str(probes), "--dir", str(self.snapdir)]), 0)

    def test_compare_detects_change(self):
        recorded = self._probes("greet\techo hello\n")
        snapshot.main(["record", "--commands", str(recorded), "--dir", str(self.snapdir)])
        changed = self._probes("greet\techo goodbye\n")
        self.assertEqual(snapshot.main(["compare", "--commands", str(changed), "--dir", str(self.snapdir)]), 1)

    def test_compare_missing_baseline_fails(self):
        probes = self._probes("never\techo nope\n")
        self.assertEqual(snapshot.main(["compare", "--commands", str(probes), "--dir", str(self.snapdir)]), 1)

    def test_mask_hides_volatile_text(self):
        recorded = self._probes("num\techo 2020\n")
        snapshot.main(["record", "--commands", str(recorded), "--dir", str(self.snapdir), "--mask", r"\d+"])
        changed = self._probes("num\techo 9999\n")
        rc = snapshot.main(["compare", "--commands", str(changed), "--dir", str(self.snapdir), "--mask", r"\d+"])
        self.assertEqual(rc, 0)

    def test_probes_parsing_derives_name(self):
        parsed = list(snapshot.probes(self._probes("# a comment\n\necho hi\nnamed\techo bye\n")))
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[1], ("named", "echo bye"))


if __name__ == "__main__":
    unittest.main()
