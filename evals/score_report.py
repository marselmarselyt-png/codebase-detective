#!/usr/bin/env python3
"""Score an investigation report against the skill's rules.

Checks what can be checked mechanically: required sections, file:line citations,
quoted exit codes, honest uncertainty. It cannot tell you whether the root cause
is *correct* - that is a human judgement against tests/BUGS.md.

Usage:
    python3 score_report.py --report REPORT.md
    python3 score_report.py --report REPORT.md --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys

CITATION = re.compile(r"[\w./-]+\.\w{1,6}:\d+")
EXIT_CODE = re.compile(r"exit(?:\s+code)?\s*[:=]?\s*(\d+)", re.I)
BANNED = {
    "claims a passing suite without an exit code": re.compile(
        r"(?<!no )tests? (?:pass|passed)(?![^\n]{0,40}(exit|code))", re.I
    ),
    "asserts certainty language": re.compile(
        r"\b(obviously|clearly the (?:root )?(?:bug|cause)|definitely the root cause)\b", re.I
    ),
    "hedges with 'should pass' instead of a result": re.compile(
        r"\bshould (?:now )?pass\b", re.I
    ),
}

REQUIRED_SECTIONS = [
    "symptom",
    "evidence",
    "root cause",
    "impact",
    "change made",
    "verification",
    "risk",
    "confidence",
]

CHECKS = [
    ("root cause section present", lambda t: "root cause" in t.lower()),
    ("verification section present", lambda t: "verification" in t.lower()),
    ("evidence section present", lambda t: "evidence" in t.lower()),
    ("cites at least 3 file:line references", lambda t: len(set(CITATION.findall(t))) >= 3),
    ("quotes a real exit code", lambda t: bool(EXIT_CODE.search(t))),
    ("states a confidence level", lambda t: bool(
        re.search(r"confidence[^\n]{0,24}\b(HIGH|MEDIUM|LOW|CAUSE NOT FOUND)\b", t, re.I)
    )),
    ("marks not-run work as NOT RUN", lambda t: (
        "not run" in t.lower() or bool(EXIT_CODE.search(t))
    )),
    ("lists remaining risks", lambda t: bool(re.search(r"remaining risk|risks?\b", t, re.I))),
]


def score(text: str) -> dict:
    results = []
    for name, fn in CHECKS:
        results.append({"check": name, "pass": bool(fn(text))})
    violations = []
    for name, pat in BANNED.items():
        hits = pat.findall(text)
        if hits:
            violations.append({"violation": name, "matches": hits[:5]})

    passed = sum(1 for r in results if r["pass"])
    total = len(results)
    penalty = len(violations) * 2
    pct = max(0, round(100 * (passed / total) - penalty * 5))
    return {
        "checks": results,
        "violations": violations,
        "score": pct,
        "passed": f"{passed}/{total}",
        "verdict": (
            "STRONG" if pct >= 85 else "ACCEPTABLE" if pct >= 60 else "WEAK - skill not followed"
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Score an investigation report.")
    ap.add_argument("--report", required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        with open(args.report, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        print(f"cannot read report: {exc}", file=sys.stderr)
        return 2

    result = score(text)
    missing = [s for s in REQUIRED_SECTIONS if s not in text.lower()]
    result["missing_sections"] = missing

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    print(f"REPORT SCORE: {result['score']}%  ({result['passed']} checks)  {result['verdict']}")
    print("=" * 72)
    for c in result["checks"]:
        print(f"  [{'x' if c['pass'] else ' '}] {c['check']}")
    if missing:
        print("\n  missing sections: " + ", ".join(missing))
    if result["violations"]:
        print("\n  VIOLATIONS")
        for v in result["violations"]:
            print(f"  ! {v['violation']}: {v['matches']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())