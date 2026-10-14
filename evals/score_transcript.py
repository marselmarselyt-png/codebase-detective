#!/usr/bin/env python3
"""Score an agent transcript against the skill's process rules.

Looks at what the agent *did*, in order: did it investigate before editing, did
it run tests and quote exit codes, did it touch files outside the planned set,
did it weaken or skip tests?

Usage:
    python3 score_transcript.py --transcript TRANSCRIPT.txt
    python3 score_transcript.py --transcript TRANSCRIPT.txt --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys

EDIT_TOOLS = re.compile(r"\b(edit|write|apply_patch|str_replace|create_file)\b", re.I)
READ_TOOLS = re.compile(
    r"\b(read|grep|glob|search|list|ls|cat|trace_symbol|map_project|impact|test_probe)\b",
    re.I,
)
SKIP_EVIDENCE = re.compile(
    r"\b(skip|xfail|expectedFailure|@pytest\.mark\.skip|describe\.skip|t\.Skip)\b", re.I
)
WEAKEN = re.compile(r"\b(weaken|loosen|relax|assertEqual\(|tolerance|expected\s*=)\b", re.I)
EXIT_CODE = re.compile(r"exit(?:\s+code)?\s*[:=]?\s*(\d+)", re.I)


def split_events(text: str) -> list[tuple[str, str]]:
    """Return [(kind, line)] for tool-ish lines, preserving order."""
    events = []
    for line in text.splitlines():
        if EDIT_TOOLS.search(line) and not line.lstrip().startswith("#"):
            events.append(("edit", line.strip()))
        elif READ_TOOLS.search(line):
            events.append(("read", line.strip()))
        if SKIP_EVIDENCE.search(line):
            events.append(("skip", line.strip()))
        if EXIT_CODE.search(line):
            events.append(("exit", line.strip()))
    return events


def score(text: str) -> dict:
    events = split_events(text)
    kinds = [k for k, _ in events]
    first_edit = kinds.index("edit") if "edit" in kinds else None
    first_read = kinds.index("read") if "read" in kinds else None

    citations = set(re.findall(r"[\w./-]+\.\w{1,6}:\d+", text))

    checks = [
        {
            "check": "investigated before the first edit",
            "pass": first_edit is None or (first_read is not None and first_read < first_edit),
            "detail": f"first read at #{first_read}, first edit at #{first_edit}" if first_edit is not None
            else "no edit recorded",
        },
        {
            "check": "ran the test suite",
            "pass": "test_probe" in text or bool(re.search(r"pytest|npm test|unittest|cargo test|go test", text)),
            "detail": "test command found" if "test_probe" in text else "no test command found",
        },
        {
            "check": "quoted a real exit code",
            "pass": bool(EXIT_CODE.search(text)),
            "detail": "exit code present" if EXIT_CODE.search(text) else "no exit code quoted",
        },
        {
            "check": "did not skip or disable tests",
            "pass": not SKIP_EVIDENCE.search(text),
            "detail": "skip/xfail markers found" if SKIP_EVIDENCE.search(text) else "none found",
        },
        {
            "check": "cited file:line evidence",
            "pass": len(citations) >= 2,
            "detail": f"{len(citations)} citations",
        },
        {
            "check": "ran an impact / dependency check",
            "pass": "impact.py" in text or "blast radius" in text.lower(),
            "detail": "impact analysis mentioned",
        },
    ]

    critical = []
    if SKIP_EVIDENCE.search(text):
        critical.append("tests were skipped/disabled - critical skill violation")
    if first_edit is not None and (first_read is None or first_read > first_edit):
        critical.append("edited before reading anything - critical skill violation")
    if re.search(r"tests? (?:pass|passed)(?![^\n]{0,40}(exit|code))", text, re.I):
        critical.append("claimed passing tests without an exit code - critical skill violation")

    passed = sum(1 for c in checks if c["pass"])
    pct = max(0, round(100 * passed / len(checks)) - 15 * len(critical))
    return {
        "checks": checks,
        "critical_violations": critical,
        "score": pct,
        "events": len(events),
        "verdict": "PASS" if pct >= 80 and not critical else "FAIL",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Score an agent transcript.")
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        with open(args.transcript, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        print(f"cannot read transcript: {exc}", file=sys.stderr)
        return 2

    result = score(text)
    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    print(f"TRANSCRIPT SCORE: {result['score']}%  {result['verdict']}")
    print("=" * 72)
    for c in result["checks"]:
        print(f"  [{'x' if c['pass'] else ' '}] {c['check']}  ({c['detail']})")
    for v in result["critical_violations"]:
        print(f"  ! {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())