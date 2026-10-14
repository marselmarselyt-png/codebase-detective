#!/usr/bin/env python3
"""Phase 7: run the tests that actually exist and report what actually happened.

The contract of this script: it never guesses. It records the literal command,
the real exit code, and real output. If it could not run anything, it says
NOT RUN. Reports built from its output may state a test passed only when
exit_code == 0.

Usage:
    python3 test_probe.py --root . --list                 # what can be run
    python3 test_probe.py --root . --run                  # run the detected suite
    python3 test_probe.py --root . --run --json
    python3 test_probe.py --root . --run --baseline before.json   # capture baseline
    python3 test_probe.py --root . --run --compare after.json      # compare vs baseline
    python3 test_probe.py --root . --cmd "npm test -- --runInBand" # run an explicit command
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import is_test_path, iter_files, read_text, truncate  # noqa: E402

MAX_OUTPUT = 20000


def detect_suites(root: str, files: list[str]) -> list[dict]:
    """Return runnable test commands detected from manifests and file layout."""
    suites: list[dict] = []
    has = lambda name: os.path.exists(os.path.join(root, name))  # noqa: E731

    pkg_path = os.path.join(root, "package.json")
    if has("package.json"):
        try:
            pkg = json.loads(read_text(pkg_path))
        except (OSError, ValueError):
            pkg = {}
        scripts = pkg.get("scripts") or {}
        merged = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        if "vitest" in merged:
            suites.append({"framework": "vitest", "cmd": "npx vitest run", "confidence": "high"})
        elif "jest" in merged:
            suites.append({"framework": "jest", "cmd": "npx jest", "confidence": "high"})
        elif "mocha" in merged:
            suites.append({"framework": "mocha", "cmd": "npx mocha", "confidence": "medium"})
        for name in ("test", "test:unit", "test:ci"):
            if name in scripts:
                suites.append(
                    {
                        "framework": f"npm script:{name}",
                        "cmd": f"npm run {name}",
                        "confidence": "medium",
                        "note": "verify what this script actually runs before trusting it",
                    }
                )

    py_files = [f for f in files if f.endswith(".py")]
    py_tests = [f for f in py_files if is_test_path(f, root)]
    if py_tests:
        pytest_cfg = has("pytest.ini") or has("setup.cfg") or (
            has("pyproject.toml") and "[tool.pytest" in read_text(os.path.join(root, "pyproject.toml"))
        )
        pytest_installed = module_available("pytest")
        if pytest_cfg or pytest_installed:
            suites.append({"framework": "pytest", "cmd": "python3 -m pytest -q", "confidence": "high"})
        else:
            suites.append({
                "framework": "unittest",
                "cmd": "python3 -m unittest discover -q",
                "confidence": "high",
                "note": "pytest config absent and pytest is not installed in this environment"
                if not pytest_cfg else "pytest config absent",
            })

    if has("Cargo.toml"):
        suites.append({"framework": "cargo", "cmd": "cargo test", "confidence": "high"})
    if has("go.mod"):
        suites.append({"framework": "go", "cmd": "go test ./...", "confidence": "high"})
    if has("pom.xml"):
        suites.append({"framework": "maven", "cmd": "mvn -q test", "confidence": "medium"})
    if has("build.gradle") or has("build.gradle.kts"):
        suites.append({"framework": "gradle", "cmd": "./gradlew test", "confidence": "medium"})
    if has("mix.exs"):
        suites.append({"framework": "exunit", "cmd": "mix test", "confidence": "medium"})

    return suites


def module_available(name: str) -> bool:
    """True if `python3 -m <name>` would actually import.

    Without this check the probe would happily run `python3 -m pytest` on a
    machine with no pytest and report the resulting ModuleNotFoundError as a
    test failure. That is exactly the kind of invented result this skill exists
    to prevent.
    """
    try:
        return subprocess.run(
            [sys.executable, "-c", f"import {name}"],
            capture_output=True, timeout=20,
        ).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def run_command(cmd: str, root: str, timeout: int) -> dict:
    """Run for real. Never fabricate a result: exit code is what the OS says."""
    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "command": cmd,
            "cwd": root,
            "exit_code": None,
            "status": "TIMEOUT",
            "duration_s": round(time.time() - started, 2),
            "timeout_s": timeout,
            "output": truncate((exc.stdout or "") + (exc.stderr or ""), MAX_OUTPUT),
        }
    except OSError as exc:
        return {
            "command": cmd,
            "cwd": root,
            "exit_code": None,
            "status": "NOT RUN",
            "duration_s": round(time.time() - started, 2),
            "error": f"{type(exc).__name__}: {exc}",
            "output": "",
        }
    combined = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    return {
        "command": cmd,
        "cwd": root,
        "exit_code": proc.returncode,
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "duration_s": round(time.time() - started, 2),
        "output": truncate(combined, MAX_OUTPUT),
        "failing_lines": [ln.strip() for ln in combined.splitlines()
                          if re_fail(ln)][:40],
    }


def re_fail(line: str) -> bool:
    low = line.lower()
    markers = ("fail", "error", "assertionerror", "traceback", "✗", "×", "not ok")
    return any(m in low for m in markers)


def compare(baseline: dict, current: dict) -> dict:
    """Diff two runs: did our change introduce failures, or remove them?"""
    def fails(run: dict) -> set[str]:
        return set(run.get("failing_lines") or [])

    def failing_test_ids(run: dict) -> set[str]:
        ids = set()
        for line in run.get("failing_lines") or []:
            for tok in line.replace("::", " ").split():
                if tok.startswith(("test_", "Test", "should", "it(")) or ".test." in tok:
                    ids.add(tok.strip("[]()"))
        return ids

    b, c = fails(baseline), fails(current)
    return {
        "baseline_exit_code": baseline.get("exit_code"),
        "current_exit_code": current.get("exit_code"),
        "new_failures": sorted(c - b)[:40],
        "fixed_failures": sorted(b - c)[:40],
        "regressions": "NONE" if c <= b else "POSSIBLE REGRESSION - inspect new_failures",
        "verdict": (
            "no new failures"
            if c <= b
            else "new failures appeared; determine whether your change caused them"
        ),
        "reminder": "compare against the same command, same machine, same scope",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Discover and run real tests; report real exit codes.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--list", action="store_true", help="show detected test commands")
    ap.add_argument("--run", action="store_true", help="execute the detected (or given) command")
    ap.add_argument("--cmd", help="run this exact command instead of a detected one")
    ap.add_argument("--framework", help="pick a detected framework by name")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--baseline", help="write this run to a baseline JSON file")
    ap.add_argument("--compare", help="compare this run against a baseline JSON file")
    ap.add_argument("--save", help="write this run's result to a JSON file")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    files = list(iter_files(root))

    if args.list or (not args.run and not args.cmd):
        suites = detect_suites(root, files)
        if args.json:
            print(json.dumps({"root": root, "suites": suites}, indent=2))
            return 0
        print(f"TEST SETUPS DETECTED in {root}")
        print("=" * 72)
        if not suites:
            print("  (none detected - no test framework found)")
            print("  consequence: there is NO automated verification available.")
            print("  Do not claim the change is verified. Report NOT RUN.")
            return 0
        for s in suites:
            print(f"  {s['framework']:<24} {s['cmd']:<40} confidence={s['confidence']}")
            if s.get("note"):
                print(f"      note: {s['note']}")
        print("")
        print("Run one with: python3 test_probe.py --root . --run --framework <name>")
        return 0

    if args.cmd:
        cmd = args.cmd
    else:
        suites = detect_suites(root, files)
        if args.framework:
            match = [s for s in suites if args.framework.lower() in s["framework"].lower()]
            if not match:
                print(f"framework '{args.framework}' not detected; available: "
                      f"{[s['framework'] for s in suites]}", file=sys.stderr)
                return 2
            cmd = match[0]["cmd"]
        elif suites:
            cmd = suites[0]["cmd"]
        else:
            print("NO TEST FRAMEWORK DETECTED - nothing to run. Report NOT RUN.", file=sys.stderr)
            return 3

    print(f"$ (cd {root} && {cmd})", file=sys.stderr)
    result = run_command(cmd, root, args.timeout)
    result["argv"] = shlex.split(cmd)

    if args.compare:
        try:
            with open(args.compare, "r", encoding="utf-8") as fh:
                baseline = json.load(fh)
        except (OSError, ValueError) as exc:
            print(f"cannot read baseline {args.compare}: {exc}", file=sys.stderr)
            return 2
        result["comparison"] = compare(baseline, result)

    for target in filter(None, [args.baseline, args.save]):
        with open(target, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("=" * 72)
        print(f"COMMAND   : {result['command']}")
        print(f"CWD       : {result['cwd']}")
        print(f"EXIT CODE : {result['exit_code']}")
        print(f"STATUS    : {result['status']}   ({result['duration_s']}s)")
        if result.get("failing_lines"):
            print("FAILURE LINES (verbatim from output):")
            for ln in result["failing_lines"]:
                print(f"  {ln}")
        if "comparison" in result:
            c = result["comparison"]
            print(f"BASELINE  : exit={c['baseline_exit_code']} -> now exit={c['current_exit_code']}")
            print(f"VERDICT   : {c['verdict']}")
            if c["new_failures"]:
                print("NEW FAILURES:")
                for f in c["new_failures"]:
                    print(f"  + {f}")
        print("-" * 72)
        print(result.get("output", "").strip()[-8000:])
        print("-" * 72)
        print("REPORTING RULE: state PASS only if EXIT CODE is 0. Otherwise paste the")
        print("real status. If no framework exists, the status is NOT RUN.")

    return 0 if result["exit_code"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())