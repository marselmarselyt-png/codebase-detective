#!/usr/bin/env python3
"""Phases 2 and 4: dependency map and blast-radius analysis.

--list   print the import graph, hotspots and public surfaces (phase 2).
--files  given files you intend to edit, report who depends on them, how deep
         the transitive dependents go, which tests cover them, and a risk tier
         (phase 4). Always run this BEFORE editing.

Usage:
    python3 impact.py --root . --list
    python3 impact.py --root . --files src/pricing.py src/cart.py --json
    python3 impact.py --root . --files src/pricing.py --symbols apply_discount
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict, deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (  # noqa: E402
    extract_exports,
    extract_imports,
    is_test_path,
    iter_files,
    language_of,
    read_lines,
    resolve_module,
)

MAX_DEPTH = 6


def build_graph(root: str, files: list[str]) -> dict:
    """edges[a] = set of files a imports; incoming[a] = files importing a."""
    outgoing: dict[str, set[str]] = defaultdict(set)
    incoming: dict[str, set[str]] = defaultdict(set)
    unresolved: dict[str, list[str]] = {}
    exports: dict[str, list[str]] = {}
    known = set(files)
    for rel in files:
        try:
            lines = read_lines(os.path.join(root, rel))
        except OSError:
            continue
        exports[rel] = extract_exports(rel, lines)
        for mod in extract_imports(rel, lines):
            target = resolve_module(mod, rel, known)
            if target and target != rel:
                outgoing[rel].add(target)
                incoming[target].add(rel)
            else:
                unresolved.setdefault(rel, []).append(mod)
    return {
        "root": root,
        "outgoing": {k: sorted(v) for k, v in outgoing.items() if v},
        "incoming": {k: sorted(v) for k, v in incoming.items() if v},
        "unresolved": unresolved,
        "exports": exports,
    }


def hotspots(graph: dict, limit: int = 15) -> list[dict]:
    root = graph.get("root", os.getcwd())
    incoming = graph["incoming"]
    out = []
    for f, deps in incoming.items():
        if is_test_path(f, root):
            continue
        out.append({"file": f, "imported_by": len(deps), "dependents_sample": sorted(deps)[:5]})
    out.sort(key=lambda d: -d["imported_by"])
    return out[:limit]


def dependents(graph: dict, seeds: list[str]) -> dict[str, list[str]]:
    """Transitive reverse dependencies, BFS, with the shortest path recorded."""
    incoming = graph["incoming"]
    paths: dict[str, list[str]] = {}
    queue = deque((s, [s]) for s in seeds)
    seen = set(seeds)
    while queue:
        node, path = queue.popleft()
        for parent in incoming.get(node, []):
            if parent in seen:
                continue
            seen.add(parent)
            new_path = [parent] + path
            paths[parent] = new_path
            if len(new_path) - 1 < MAX_DEPTH:
                queue.append((parent, new_path))
    return paths


def tests_covering(graph: dict, seeds: list[str]) -> dict[str, list[str]]:
    deps = dependents(graph, seeds)
    direct = sorted({f for f in list(seeds) + list(deps) if is_test_path(f)})
    indirect: set[str] = set()
    for f in deps:
        if is_test_path(f):
            continue
        for parent in graph["incoming"].get(f, []):
            if is_test_path(parent):
                indirect.add(f"{parent} (via {f})")
    return {"direct_tests": direct, "transitive_tests": sorted(indirect)}


TIERS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

STDLIB_HINT = {
    "__future__", "abc", "argparse", "asyncio", "collections", "contextlib", "csv",
    "dataclasses", "datetime", "enum", "functools", "glob", "hashlib", "io", "itertools",
    "json", "logging", "math", "os", "pathlib", "random", "re", "shlex", "shutil",
    "socket", "sqlite3", "string", "subprocess", "sys", "tempfile", "textwrap",
    "threading", "time", "traceback", "types", "typing", "unittest", "urllib", "uuid",
    "warnings", "xml", "zipfile", "http", "json", "logging", "unittest", "platform",
    "inspect", "ast", "operator", "statistics", "secrets", "copy",
}


def bump(tier: str) -> str:
    idx = TIERS.index(tier)
    return TIERS[min(idx + 1, len(TIERS) - 1)]


def risk_tier(changed: list[str], deps: dict, coverage: dict, graph: dict) -> tuple[str, list[str]]:
    root = graph.get("root", os.getcwd())
    reasons: list[str] = []
    n_prod = [d for d in deps if not is_test_path(d, root)]
    n_test = [d for d in deps if is_test_path(d, root)]
    edges_out = sum(len(graph["outgoing"].get(f, [])) for f in changed)

    score = len(n_prod) * 2 + len(n_test) + edges_out
    if score == 0:
        tier = "LOW"
        reasons.append("leaf module: nothing inside the repo imports it")
    elif score <= 5:
        tier = "MEDIUM"
    elif score <= 20:
        tier = "HIGH"
    else:
        tier = "CRITICAL"

    if any("__init__" in f or f.endswith("index") or "public" in f.lower() for f in changed):
        reasons.append("a package entry point is changing: everything downstream sees it")
        tier = bump(tier)
    if n_prod:
        reasons.append(f"{len(n_prod)} production dependent(s) within {MAX_DEPTH} hops")
    if n_test:
        reasons.append(f"{len(n_test)} test(s) reference the changed code directly")
    else:
        reasons.append("NO TEST COVERAGE found for this path - a manual check is mandatory")
        tier = bump(tier)
    if edges_out:
        reasons.append(
            f"changed files still import {edges_out} other module(s): review the whole import chain"
        )
    return tier, reasons


def analyse(root: str, files: list[str], changed: list[str], symbols: list[str]) -> dict:
    graph = build_graph(root, files)
    known = set(files)
    resolved, missing = [], []
    for c in changed:
        if c in known:
            resolved.append(c)
            continue
        alt = resolve_module(c, "", known)
        (resolved if alt else missing).append(alt or c)
    deps = dependents(graph, resolved)
    coverage = tests_covering(graph, resolved)
    tier, reasons = risk_tier(resolved, deps, coverage, graph)

    symbol_hits: dict[str, list[str]] = {}
    if symbols:
        for sym in symbols:
            hits = []
            pat = re.compile(rf"(?<![\w.]){re.escape(sym)}\b")
            for f in files:
                try:
                    for i, line in enumerate(read_lines(os.path.join(root, f)), 1):
                        if pat.search(line):
                            hits.append(f"{f}:{i}")
                except OSError:
                    continue
            symbol_hits[sym] = hits

    return {
        "changed_files": resolved,
        "unresolved_inputs": missing,
        "risk": tier,
        "risk_reasons": reasons,
        "direct_dependents": sorted(graph["incoming"].get(resolved[0], [])) if len(resolved) == 1 else [],
        "transitive_dependents": {f: path for f, path in sorted(deps.items())},
        "dependent_count": len(deps),
        "production_dependent_count": len([d for d in deps if not is_test_path(d, root)]),
        "test_coverage": coverage,
        "exported_symbols_in_changed": {f: graph["exports"].get(f, []) for f in resolved},
        "symbol_usage": symbol_hits,
        "hotspots": hotspots(graph),
        "still_imports": {f: graph["outgoing"].get(f, []) for f in resolved},
        "unresolved_imports": {f: graph["unresolved"].get(f, []) for f in resolved if graph["unresolved"].get(f)},
        "caveats": [
            "static analysis only: runtime wiring (DI, reflection, decorators, config strings, "
            "DB triggers, external callers) is invisible here",
            "cross-language and cross-repo consumers cannot be enumerated from this tree",
        ],
    }


def render_analysis(a: dict) -> str:
    out = [f"IMPACT ANALYSIS  risk={a['risk']}", "=" * 72]
    out.append("changed files : " + ", ".join(a["changed_files"]))
    if a["unresolved_inputs"]:
        out.append("UNRESOLVED    : " + ", ".join(a["unresolved_inputs"]) + "  (not in scan scope - verify manually)")
    out.append("")
    out.append("RISK REASONS")
    for r in a["risk_reasons"]:
        out.append(f"  - {r}")
    out.append("")
    out.append(f"DEPENDENTS: {a['dependent_count']} total, {a['production_dependent_count']} production")
    for f, path in list(a["transitive_dependents"].items())[:25]:
        out.append(f"  {' -> '.join(path)}")
    if not a["transitive_dependents"]:
        out.append("  (none)")
    out.append("")
    out.append("TEST COVERAGE")
    out.append("  direct     : " + (", ".join(a["test_coverage"]["direct_tests"]) or "(none)"))
    out.append("  transitive : " + (", ".join(a["test_coverage"]["transitive_tests"]) or "(none)"))
    out.append("")
    out.append("EXPORTED SYMBOLS THAT LEAVE THE MODULE")
    for f, syms in a["exported_symbols_in_changed"].items():
        out.append(f"  {f}: {', '.join(syms[:20]) or '(none)'}")
    if a["symbol_usage"]:
        out.append("")
        out.append("SYMBOL USAGE")
        for sym, hits in a["symbol_usage"].items():
            out.append(f"  {sym}: {len(hits)} reference(s)")
            for h in hits[:12]:
                out.append(f"    {h}")
    if a["unresolved_imports"]:
        out.append("")
        out.append("EXTERNAL / UNRESOLVED IMPORTS IN CHANGED FILES")
        for f, mods in a["unresolved_imports"].items():
            external = [m for m in mods if m.split(".")[0].split("/")[0] not in STDLIB_HINT]
            if external:
                out.append(f"  {f}: {', '.join(external)}")
    out.append("")
    out.append("CAVEATS (things this tool cannot see)")
    for c in a["caveats"]:
        out.append(f"  ! {c}")
    return "\n".join(out)


def render_list(graph: dict, hs: list[dict], root: str) -> str:
    out = [f"DEPENDENCY MAP  {root}", "=" * 72]
    out.append(f"modules with edges: {len(graph['outgoing'])}")
    out.append("")
    out.append("HOTSPOTS (most-imported modules - editing these is high risk)")
    for h in hs:
        out.append(f"  {h['file']:<45} imported_by={h['imported_by']}")
    if not hs:
        out.append("  (no internal import edges found - check your ignore patterns)")
    out.append("")
    out.append("MODULE EDGES")
    for f, deps in sorted(graph["outgoing"].items(), key=lambda kv: -len(kv[1]))[:40]:
        out.append(f"  {f}")
        for d in deps:
            out.append(f"      -> {d}")
    out.append("")
    out.append("NEXT: trace the suspect symbol, then analyse before editing:")
    out.append("  python3 trace_symbol.py --root . --symbol NAME")
    out.append("  python3 impact.py --root . --files a.py b.py")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Dependency map and blast-radius analysis.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--list", action="store_true", help="dependency map / hotspots (phase 2)")
    ap.add_argument("--files", nargs="*", default=[], help="files you plan to edit (phase 4)")
    ap.add_argument("--symbols", nargs="*", default=[], help="symbols whose usage to count")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    files = list(iter_files(root))

    if args.list or not args.files:
        graph = build_graph(root, files)
        if args.json:
            print(json.dumps({"root": root, "graph": graph, "hotspots": hotspots(graph)}, indent=2))
        else:
            print(render_list(graph, hotspots(graph), root))
        return 0

    result = analyse(root, files, args.files, args.symbols)
    print(json.dumps(result, indent=2) if args.json else render_analysis(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())