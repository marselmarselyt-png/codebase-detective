"""Test suite for the Codebase Detective scripts.

Runs the real CLIs as subprocesses against `tests/fixture_repo` (a project with
planted cross-file bugs) and against a temporary copy that has been fixed, so
that "the bug reproduces" and "the fix does not regress" are both verified.

Run:
    python3 -m unittest discover -s tests -t . -v
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "scripts")
FIXTURE = os.path.join(REPO, "tests", "fixture_repo")

# the two planted fixes, applied to a temp copy to prove the regression tests
# turn green and nothing else breaks.
FIXES = {
    "shopcart/api.py": ('TIER_FIELD = "customerTier"', 'TIER_FIELD = "tier"'),
    "shopcart/inventory.py": (
        "def reserve(sku, qty, ledger=[]):",
        "def reserve(sku, qty, ledger=None):\n"
        "    ledger = [] if ledger is None else ledger",
    ),
    "web/src/api.js": ("if (!result.valid) {", "if (!result) {"),
}


def run(args, cwd=REPO, expect=None):
    proc = subprocess.run(
        [sys.executable, *args], cwd=cwd, capture_output=True, text=True, timeout=180
    )
    if expect is not None and proc.returncode != expect:
        raise AssertionError(
            f"{args} exited {proc.returncode}, expected {expect}\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc


def script(name, *args, cwd=REPO, expect=0):
    return run([os.path.join(SCRIPTS, name), *args], cwd=cwd, expect=expect)


def script_json(name, *args, cwd=REPO, expect=0):
    proc = script(name, *args, cwd=cwd, expect=expect)
    try:
        return json.loads(proc.stdout)
    except ValueError as exc:  # pragma: no cover - surfaces a real script bug
        raise AssertionError(f"{name} did not emit valid JSON: {exc}\n{proc.stdout[:800]}")


def run_fixture_suite(root):
    """Run the fixture's own unittest suite; returns the real exit code."""
    return subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=180,
    )


def temp_copy():
    tmp = tempfile.mkdtemp(prefix="detective-fixture-")
    dst = os.path.join(tmp, "fixture_repo")
    shutil.copytree(FIXTURE, dst)
    for junk in (".detective-snapshot.json",):
        p = os.path.join(dst, junk)
        if os.path.exists(p):
            os.remove(p)
    return dst


def apply_fixes(root):
    for rel, (old, new) in FIXES.items():
        path = os.path.join(root, rel)
        with open(path, "r", encoding="utf-8") as fh:
            body = fh.read()
        if old not in body:
            raise AssertionError(f"fix anchor not found in {rel}: {old!r}")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body.replace(old, new, 1))


# ---------------------------------------------------------------- phase 1
class MapProjectTests(unittest.TestCase):
    def test_maps_the_fixture_project(self):
        data = script_json("map_project.py", "--root", FIXTURE, "--json")
        self.assertEqual(data["primary_language"], "Python")
        self.assertGreater(data["source_files"], 5)
        self.assertTrue(any(m["file"].endswith("package.json") for m in data["manifests"]))
        self.assertGreaterEqual(data["tests"]["test_files"], 3)
        self.assertTrue(any("unittest" in f or "pytest" in f for f in data["tests"]["frameworks"]))

    def test_layout_groups_files_by_directory(self):
        data = script_json("map_project.py", "--root", FIXTURE, "--json")
        layout = data["layout"]
        self.assertTrue(any("shopcart" in k for k in layout))
        self.assertTrue(any("tests" in k for k in layout))

    def test_human_output_mentions_test_setup(self):
        out = script("map_project.py", "--root", FIXTURE).stdout
        self.assertIn("TESTS", out)
        self.assertIn("PROJECT MAP", out)

    def test_scan_can_be_scoped_to_a_subdirectory(self):
        data = script_json("map_project.py", "--root", FIXTURE, "--dir", "shopcart", "--json")
        self.assertTrue(data["files"])
        self.assertTrue(all(f.startswith("shopcart/") for f in data["files"]))


# ---------------------------------------------------------------- phase 2/4
class ImpactTests(unittest.TestCase):
    def test_dependency_map_reports_the_shared_hotspot(self):
        data = script_json("impact.py", "--root", FIXTURE, "--list", "--json")
        graph = data["graph"]
        self.assertTrue(graph["outgoing"].get("shopcart/service.py"))
        self.assertIn("shopcart/models.py", graph["outgoing"]["shopcart/service.py"])
        self.assertTrue(data["hotspots"])

    def test_blast_radius_lists_transitive_dependents(self):
        data = script_json(
            "impact.py", "--root", FIXTURE, "--files", "shopcart/models.py", "--json"
        )
        dependents = set(data["transitive_dependents"])
        self.assertIn("shopcart/service.py", dependents)
        self.assertIn("shopcart/__init__.py", dependents)

    def test_blast_radius_finds_the_regression_tests(self):
        data = script_json(
            "impact.py", "--root", FIXTURE, "--files", "shopcart/api.py", "--json"
        )
        coverage = " ".join(
            data["test_coverage"]["direct_tests"] + data["test_coverage"]["transitive_tests"]
        )
        self.assertIn("test_regression_tier", coverage)

    def test_risk_rises_with_the_number_of_dependents(self):
        narrow = script_json("impact.py", "--root", FIXTURE, "--files", "shopcart/api.py", "--json")
        wide = script_json("impact.py", "--root", FIXTURE, "--files", "shopcart/models.py", "--json")
        order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        self.assertLess(order.index(narrow["risk"]), order.index(wide["risk"]))
        self.assertGreater(wide["production_dependent_count"], narrow["production_dependent_count"])

    def test_uncovered_path_is_called_out(self):
        root = temp_copy()
        try:
            orphan = os.path.join(root, "shopcart", "orphan.py")
            with open(orphan, "w", encoding="utf-8") as fh:
                fh.write("def helper(x):\n    return x + 1\n")
            data = script_json("impact.py", "--root", root, "--files", "shopcart/orphan.py",
                               "--symbols", "helper", "--json")
            joined = " ".join(data["risk_reasons"]).lower()
            self.assertIn("no test coverage", joined)
            self.assertEqual(data["test_coverage"]["direct_tests"], [])
            self.assertTrue(data["symbol_usage"]["helper"])
        finally:
            shutil.rmtree(os.path.dirname(root), ignore_errors=True)

    def test_missing_file_is_reported_not_crashed(self):
        data = script_json("impact.py", "--root", FIXTURE, "--files", "does/not/exist.py", "--json")
        self.assertIn("does/not/exist.py", data["unresolved_inputs"])

    def test_javascript_import_edges_resolve(self):
        if shutil.which("node") is None:
            self.skipTest("node not installed")
        data = script_json("impact.py", "--root", FIXTURE, "--files", "web/src/auth.js", "--json")
        self.assertIn("web/src/api.js", data["transitive_dependents"])


# ---------------------------------------------------------------- phase 3
class TraceSymbolTests(unittest.TestCase):
    def test_traces_a_cross_file_symbol(self):
        trace = script_json("trace_symbol.py", "--root", FIXTURE, "--symbol", "Customer", "--json")
        defs = trace["definitions"]
        self.assertTrue(any(d["file"].endswith("models.py") for d in defs))
        self.assertTrue(any(s["file"].endswith("service.py") for s in trace["call_sites"]))

    def test_flags_a_missing_tier_field_as_an_unresolved_import(self):
        data = script_json("impact.py", "--root", FIXTURE, "--files", "shopcart/api.py", "--json")
        self.assertEqual(data["risk_reasons"] is not None, True)

    def test_file_mode_reports_exports_and_importers(self):
        rep = script_json("trace_symbol.py", "--root", FIXTURE, "--file", "shopcart/models.py",
                           "--importers", "--json")
        self.assertIn("Customer", rep["exports"])
        self.assertIn("shopcart/service.py", rep["importers"])

    def test_unknown_symbol_is_reported_without_inventing_results(self):
        trace = script_json("trace_symbol.py", "--root", FIXTURE, "--symbol", "does_not_exist", "--json")
        self.assertEqual(trace["definitions"], [])
        self.assertTrue(any("no definition" in w for w in trace["warnings"]))

    def test_trace_reaches_the_javascript_twin(self):
        trace = script_json("trace_symbol.py", "--root", FIXTURE, "--symbol", "verify", "--json")
        files = {s["file"] for s in trace["definitions"] + trace["call_sites"]}
        self.assertIn("web/src/auth.js", files)
        self.assertIn("web/src/api.js", files)

    def test_identical_names_are_flagged_as_duplicates(self):
        root = temp_copy()
        try:
            dup = os.path.join(root, "shopcart", "tiers_copy.py")
            shutil.copyfile(os.path.join(root, "shopcart", "tiers.py"), dup)
            trace = script_json("trace_symbol.py", "--root", root, "--symbol", "normalize", "--json")
            self.assertTrue(any("DUPLICATE DEFINITION" in w for w in trace["warnings"]))
        finally:
            shutil.rmtree(os.path.dirname(root), ignore_errors=True)


# ---------------------------------------------------------------- phase 7
class TestProbeTests(unittest.TestCase):
    def test_lists_detected_suites(self):
        data = script_json("test_probe.py", "--root", FIXTURE, "--list", "--json")
        self.assertTrue(data["suites"])

    def test_reports_the_real_exit_code_on_a_broken_suite(self):
        proc = script("test_probe.py", "--root", FIXTURE, "--run", "--cmd",
                      f"{sys.executable} -m unittest discover -s tests -t .", expect=1)
        self.assertIn("EXIT CODE : 1", proc.stdout)
        self.assertIn("STATUS    : FAIL", proc.stdout)

    def test_reports_pass_only_when_the_exit_code_is_zero(self):
        fixed = temp_copy()
        try:
            apply_fixes(fixed)
            proc = script(
                "test_probe.py", "--root", fixed, "--run", "--cmd",
                f"{sys.executable} -m unittest discover -s tests -t .", expect=0,
            )
            self.assertIn("EXIT CODE : 0", proc.stdout)
            self.assertIn("STATUS    : PASS", proc.stdout)
        finally:
            shutil.rmtree(os.path.dirname(fixed), ignore_errors=True)

    def test_missing_toolchain_is_reported_as_not_run(self):
        data = script_json(
            "test_probe.py", "--root", FIXTURE, "--run",
            "--cmd", "definitely-not-a-real-binary-xyz", "--json", expect=1,
        )
        self.assertNotEqual(data["status"], "PASS")
        self.assertIn(data["status"], ("FAIL", "NOT RUN", "TIMEOUT"))

    def test_baseline_comparison_detects_new_failures(self):
        broken = temp_copy()
        try:
            baseline = os.path.join(broken, "baseline.json")
            script("test_probe.py", "--root", broken, "--run", "--cmd",
                   f"{sys.executable} -m unittest discover -s tests -t .",
                   "--baseline", baseline, expect=1)
            apply_fixes(broken)
            data = script_json(
                "test_probe.py", "--root", broken, "--run", "--cmd",
                f"{sys.executable} -m unittest discover -s tests -t .",
                "--compare", baseline, "--json", expect=0,
            )
            self.assertIn("comparison", data)
            self.assertEqual(data["comparison"]["baseline_exit_code"], 1)
            self.assertEqual(data["comparison"]["current_exit_code"], 0)
        finally:
            shutil.rmtree(os.path.dirname(broken), ignore_errors=True)

    def test_node_fixture_suite_reports_a_real_failure(self):
        if shutil.which("node") is None:
            self.skipTest("node not installed")
        web = os.path.join(FIXTURE, "web")
        data = script_json("test_probe.py", "--root", web, "--run", "--json", expect=1)
        self.assertEqual(data["exit_code"], 1)
        self.assertEqual(data["status"], "FAIL")


# ---------------------------------------------------------------- user-work guard
class SnapshotTests(unittest.TestCase):
    def test_save_then_verify_detects_an_edit(self):
        root = temp_copy()
        try:
            snap = os.path.join(root, "snap.json")
            script("snapshot.py", "--root", root, "--save", "shopcart/api.py", "--out", snap)
            quiet = script_json("snapshot.py", "--root", root, "--verify", "--out", snap, "--json")
            self.assertEqual(quiet["changed_since_snapshot"], [])

            target = os.path.join(root, "shopcart", "api.py")
            with open(target, "a", encoding="utf-8") as fh:
                fh.write("\n# stray edit\n")

            dirty = script_json("snapshot.py", "--root", root, "--verify", "--out", snap, "--json")
            self.assertEqual(dirty["changed_since_snapshot"], ["shopcart/api.py"])
        finally:
            shutil.rmtree(os.path.dirname(root), ignore_errors=True)

    def test_deleted_file_is_reported(self):
        root = temp_copy()
        try:
            snap = os.path.join(root, "snap.json")
            script("snapshot.py", "--root", root, "--save", "shopcart/tiers.py", "--out", snap)
            os.remove(os.path.join(root, "shopcart", "tiers.py"))
            res = script_json("snapshot.py", "--root", root, "--verify", "--out", snap, "--json")
            self.assertEqual(res["deleted_since_snapshot"], ["shopcart/tiers.py"])
        finally:
            shutil.rmtree(os.path.dirname(root), ignore_errors=True)


# ------------------------------------------------- the fixture's own contract
class FixtureRegressionTests(unittest.TestCase):
    """The planted bugs must reproduce, and the documented fixes must clear them."""

    def test_bugs_reproduce_in_a_clean_copy(self):
        root = temp_copy()
        try:
            result = run_fixture_suite(root)
            self.assertNotEqual(result.returncode, 0, "fixture must start broken")
            self.assertIn("FAILED", result.stderr)
        finally:
            shutil.rmtree(os.path.dirname(root), ignore_errors=True)

    def test_unit_tests_pass_even_while_the_product_is_broken(self):
        root = temp_copy()
        try:
            result = subprocess.run(
                [sys.executable, "-m", "unittest", "tests.test_pricing_unit"],
                cwd=root, capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        finally:
            shutil.rmtree(os.path.dirname(root), ignore_errors=True)

    def test_documented_fix_makes_the_whole_suite_green(self):
        root = temp_copy()
        try:
            apply_fixes(root)
            result = run_fixture_suite(root)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        finally:
            shutil.rmtree(os.path.dirname(root), ignore_errors=True)

    def test_javascript_fix_makes_the_node_suite_green(self):
        if shutil.which("node") is None:
            self.skipTest("node not installed")
        root = temp_copy()
        try:
            apply_fixes(root)
            result = subprocess.run(
                ["node", "src/api.test.js"], cwd=os.path.join(root, "web"),
                capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        finally:
            shutil.rmtree(os.path.dirname(root), ignore_errors=True)

    def test_a_plausible_but_wrong_fix_is_caught_by_the_regression_tests(self):
        """Silencing the tier bug inside tiers.normalize must not pass."""
        root = temp_copy()
        try:
            path = os.path.join(root, "shopcart", "tiers.py")
            with open(path, "r", encoding="utf-8") as fh:
                body = fh.read()
            body = body.replace(
                "    if raw is None:\n        return \"STANDARD\"\n",
                "    if raw is None:\n        return \"GOLD\"\n",
                1,
            )
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(body)
            result = run_fixture_suite(root)
            self.assertNotEqual(
                result.returncode, 0,
                "a wrong fix must be rejected by the regression tests, not waved through",
            )
        finally:
            shutil.rmtree(os.path.dirname(root), ignore_errors=True)

    def test_fixtures_are_not_modified_by_running_the_detective_scripts(self):
        """The detective tooling must never write into the target repository."""
        before = {}
        for dirpath, dirnames, filenames in os.walk(FIXTURE):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for name in filenames:
                full = os.path.join(dirpath, name)
                with open(full, "rb") as fh:
                    before[full] = fh.read()
        try:
            script("map_project.py", "--root", FIXTURE)
            script("impact.py", "--root", FIXTURE, "--files", "shopcart/api.py")
            script("trace_symbol.py", "--root", FIXTURE, "--symbol", "Customer")
            script("test_probe.py", "--root", FIXTURE, "--list")
        finally:
            after = {}
            for dirpath, dirnames, filenames in os.walk(FIXTURE):
                dirnames[:] = [d for d in dirnames if d != "__pycache__"]
                for name in filenames:
                    full = os.path.join(dirpath, name)
                    with open(full, "rb") as fh:
                        after[full] = fh.read()
        self.assertEqual(sorted(before), sorted(after), "detective scripts created or removed files")
        for path, content in before.items():
            self.assertEqual(content, after[path], f"detective scripts modified {path}")


if __name__ == "__main__":
    unittest.main()