#!/usr/bin/env python3
"""Phase 3: trace a symbol (or a file) across files to find the root cause.

Given a name from a log, stack trace or bug report, this prints every place
that name is defined, imported, called or referenced - each with file:line, so
a hypothesis can be built on evidence instead of on a hunch.

Usage:
    python3 trace_symbol.py --root . --symbol apply_discount
    python3 trace_symbol.py --root . --symbol apply_discount --json
    python3 trace_symbol.py --root . --file src/checkout.ts        # that file's imports/exports
    python3 trace_symbol.py --root . --file src/pricing.py --importers
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (  # noqa: E402
    Symbol,
    dialect_of,
    extract_exports,
    extract_imports,
    is_test_path,
    iter_files,
    language_of,
    read_lines,
    resolve_module,
    strip_comments_python,
    truncate,
)

DEF_PATTERNS = {
    "python": [
        re.compile(r"^\s*def\s+(\w+)\s*\("),
        re.compile(r"^\s*(?:async\s+)?def\s+(\w+)\s*\("),
        re.compile(r"^\s*class\s+(\w+)\s*[\(:]"),
        re.compile(r"^(\w+)\s*(?::[^=]+)?=\s*"),  # module level constant
    ],
    "js": [
        re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*(\w+)"),
        re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*="),
        re.compile(r"^\s*(?:export\s+)?class\s+(\w+)"),
        re.compile(r"^\s*(\w+)\s*[:(]\s*(?:async\s*)?\("),  # class/object method
    ],
    "go": [
        re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?(\w+)"),
        re.compile(r"^\s*type\s+(\w+)\s+"),
    ],
    "rust": [re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:fn|struct|enum|trait|const|static|mod|type)\s+(\w+)")],
    "java": [re.compile(r"^\s*(?:public|private|protected)?\s*(?:static\s+)?[\w<>\[\],.]+\s+(\w+)\s*\(")],
    "ruby": [re.compile(r"^\s*def\s+([\w.?!]+)")],
    "php": [re.compile(r"^\s*(?:public|private|protected|static|\s)*function\s+(\w+)\s*\(")],
}

WORD = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def scan_symbol(root: str, name: str, files: list[str]) -> dict:
    if not WORD.match(name):
        return {"symbol": name, "error": "not a plain identifier; quote the exact name"}
    found: list[Symbol] = []
    for rel in files:
        full = os.path.join(root, rel)
        try:
            lines = read_lines(full)
        except OSError:
            continue
        dialect = dialect_of(rel)
        defs = DEF_PATTERNS.get(dialect, [])
        exports = set(extract_exports(rel, lines))
        clean = [strip_comments_python(l) if dialect == "python" else l for l in lines]
        for idx, raw in enumerate(clean):
            line_no = idx + 1
            kind = None
            for pat in defs:
                m = pat.match(raw)
                if m and m.group(1) == name:
                    kind = "definition"
                    exported = name in exports
                    break
            if kind is None:
                quoted = raw.strip()[:160]
                if re.search(rf"(?<![\w.$]){re.escape(name)}\s*[(!]", raw):
                    kind = "test" if is_test_path(rel, root) else "call"
                elif re.search(rf"(?<![\w.]){re.escape(name)}\b", raw):
                    kind = "test" if is_test_path(rel, root) else "reference"
                if kind:
                    found.append(Symbol(name, rel, line_no, kind, False, quoted))
                    continue
            else:
                found.append(Symbol(name, rel, line_no, kind, exported, raw.strip()[:160]))

    grouped: dict[str, list[Symbol]] = {}
    for s in found:
        grouped.setdefault(s.kind, []).append(s)

    defs = grouped.get("definition", [])
    return {
        "symbol": name,
        "counts": {k: len(v) for k, v in grouped.items()},
        "definitions": [s.to_dict() for s in defs],
        "call_sites": [s.to_dict() for s in grouped.get("call", [])],
        "references": [s.to_dict() for s in grouped.get("reference", [])],
        "tests": [s.to_dict() for s in grouped.get("test", [])],
        "files_touched": sorted({s.file for s in found}),
        "warnings": _warnings(defs, found, root),
        "interpretation": _interpret(defs, found, grouped),
    }


def _warnings(defs: list[Symbol], all_found: list[Symbol], root: str) -> list[str]:
    out = []
    if len(defs) > 1:
        out.append(
            "DUPLICATE DEFINITION: " + ", ".join(f"{d.file}:{d.line}" for d in defs)
            + " - the same name is defined more than once; one shadow may be dead code"
        )
    if not defs:
        out.append("no definition found - it may be injected (DI/reflection), dynamic, or external")
    files = {s.file for s in all_found}
    if any(is_test_path(f, root) for f in files):
        out.append("touched by tests - run them before and after any change")
    return out


def _interpret(defs: list[Symbol], all_found: list[Symbol], grouped: dict) -> list[str]:
    """Plain-language reading of the trace, so the agent does not misread it."""
    notes = []
    calls = grouped.get("call", [])
    if defs and calls:
        by_file: dict[str, list[Symbol]] = {}
        for c in calls:
            by_file.setdefault(c.file, []).append(c)
        cross = {f: v for f, v in by_file.items() if f != defs[0].file}
        if len(cross) > 1:
            notes.append(
                f"{len(calls)} call site(s) across {len(cross)} files other than the definition: "
                "a contract change ripples outside its own module"
            )
        elif cross:
            notes.append(
                "called from another module: a contract change here is visible to that caller"
            )
        else:
            notes.append("all call sites live in the defining file: local bug, low ripple")
    if grouped.get("test"):
        notes.append(f"{len(grouped['test'])} test reference(s): this path is supposed to be covered - check the assertion, it may encode the bug")
    if defs and any(d.exported for d in defs):
        notes.append("symbol is exported: it is part of the module's public surface, treat the change as API-visible")
    if not calls and defs:
        notes.append("no call sites found statically: may be invoked dynamically - grep for string references before assuming it is unused")
    return notes


def file_report(root: str, target: str, files: list[str], show_importers: bool) -> dict:
    full = os.path.join(root, target)
    if not os.path.isfile(full):
        return {"file": target, "error": "not found"}
    lines = read_lines(full)
    imports = extract_imports(target, lines)
    exports = extract_exports(target, lines)
    modules = {}
    known = set(files)
    for f in files:
        if f == target:
            continue
        modules[f] = {
            m: resolve_module(m, f, known)
            for m in extract_imports(f, read_lines(os.path.join(root, f)))
        }
    resolved = {m: resolve_module(m, target, known) for m in imports}
    importers = []
    if show_importers:
        for f, imps in modules.items():
            for m, dest in imps.items():
                if dest == target:
                    importers.append(f)
    return {
        "file": target,
        "language": language_of(target),
        "is_test": is_test_path(target, root),
        "lines": len(lines),
        "imports": imports,
        "imports_resolved": resolved,
        "exports": exports,
        "public_surface": exports,
        "importers": sorted(set(importers)),
    }


def render(trace: dict) -> str:
    if trace.get("error"):
        return f"ERROR: {trace['error']}"
    out = [f"SYMBOL TRACE: {trace['symbol']}", "=" * 72]
    counts = trace["counts"]
    out.append(
        "counts: "
        + ", ".join(f"{k}={v}" for k, v in counts.items())
        if counts
        else "counts: (nothing found anywhere)"
    )
    for label, key in (("DEFINITIONS", "definitions"), ("CALL SITES", "call_sites"),
                       ("REFERENCES", "references"), ("TEST REFERENCES", "tests")):
        items = trace[key]
        if not items:
            continue
        out.append("")
        out.append(f"{label} ({len(items)})")
        for s in items:
            out.append(f"  {s['file']}:{s['line']}  {s['quote']}")
    if trace["warnings"]:
        out.append("")
        out.append("WARNINGS")
        for w in trace["warnings"]:
            out.append(f"  ! {w}")
    if trace["interpretation"]:
        out.append("")
        out.append("READING")
        for n in trace["interpretation"]:
            out.append(f"  - {n}")
    out.append("")
    out.append("NEXT: pick the definition you believe is on the failing path and run")
    out.append("  trace_symbol.py --file <that file> --importers   to see who depends on it")
    out.append("  impact.py --files <files you plan to edit>          to see the blast radius")
    return "\n".join(out)


def render_file(rep: dict) -> str:
    if rep.get("error"):
        return f"ERROR: {rep['error']}"
    out = [f"FILE TRACE: {rep['file']}", "=" * 72]
    out.append(f"language: {rep['language']}   lines: {rep['lines']}   test file: {rep['is_test']}")
    out.append("")
    out.append("EXPORTS (public surface)")
    out.append("\n".join(f"  - {e}" for e in rep["exports"]) or "  (none)")
    out.append("")
    out.append("IMPORTS")
    for mod, res in rep["imports_resolved"].items():
        out.append(f"  {mod:<40} -> {res or '(external / unresolved)'}")
    if rep["importers"]:
        out.append("")
        out.append("IMPORTED BY")
        out.extend(f"  - {f}" for f in rep["importers"])
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Trace symbols and files across a codebase.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--symbol", help="identifier to trace")
    ap.add_argument("--file", help="file to inspect (imports/exports/importers)")
    ap.add_argument("--importers", action="store_true", help="with --file, also list who imports it")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    files = list(iter_files(root))

    if args.file:
        rep = file_report(root, args.file, files, args.importers)
        print(json.dumps(rep, indent=2) if args.json else render_file(rep))
        return 0
    if not args.symbol:
        ap.error("provide --symbol NAME or --file PATH")

    trace = scan_symbol(root, args.symbol, files)
    print(json.dumps(trace, indent=2) if args.json else truncate(render(trace), 12000))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())