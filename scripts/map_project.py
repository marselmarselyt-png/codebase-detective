#!/usr/bin/env python3
"""Phase 1: map a project's structure before touching any code.

Answers, for an unfamiliar repository: what languages are in play, where the
entry points are, how modules are laid out, how big each area is, what test
setup exists, which files look generated, and what a previous agent or
developer has already modified in the working tree.

Usage:
    python3 map_project.py --root .                 # human summary
    python3 map_project.py --root . --json          # machine readable
    python3 map_project.py --root . --depth 2       # folder layout only
    python3 map_project.py --root . --dir src      # scope the scan
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (  # noqa: E402
    MANIFESTS,
    dialect_of,
    is_generated,
    is_test_path,
    iter_files,
    language_of,
    read_text,
    truncate,
)


def detect_entry_points(root: str, files: list[str]) -> list[dict]:
    """Package bins, main guards, __main__, and conventional server files."""
    entries: list[dict] = []

    pkg = os.path.join(root, "package.json")
    if os.path.isfile(pkg):
        try:
            data = json.loads(read_text(pkg))
        except (OSError, ValueError):
            data = {}
        bins = data.get("bin")
        if isinstance(bins, dict):
            for name, target in bins.items():
                entries.append({"kind": "npm bin", "name": name, "location": target})
        elif isinstance(bins, str):
            entries.append({"kind": "npm bin", "name": data.get("name", "bin"), "location": bins})
        main = data.get("main")
        if main:
            entries.append({"kind": "npm main", "name": data.get("name", "?"), "location": main})
        if data.get("type") == "module" or data.get("scripts"):
            entries.append({"kind": "npm scripts", "name": ", ".join(sorted(data.get("scripts", {}))[:8]), "location": "package.json"})

    for rel in files:
        base = os.path.basename(rel)
        dialect = dialect_of(rel)
        if is_test_path(rel, root):
            continue  # a test file with a main guard is not an entry point
        try:
            head = read_text(os.path.join(root, rel))[:4000]
        except OSError:
            continue
        if '__name__ == "__main__"' in head or "__name__ == '__main__'" in head:
            entries.append({"kind": "python main", "name": base, "location": rel})
        elif re.search(r"^\s*if\s+__name__", head, re.M):
            entries.append({"kind": "python entry", "name": base, "location": rel})
        if base in ("main.go", "main.rs", "main.py", "server.js", "server.ts", "app.py", "index.js", "index.ts", "main.ts"):
            entries.append({"kind": "conventional entry", "name": base, "location": rel})
        if dialect in ("go", "rust") and base == "main":
            entries.append({"kind": f"{dialect} binary", "name": base, "location": rel})
    return entries[:40]


def detect_tests(root: str, files: list[str]) -> dict:
    test_files = [f for f in files if is_test_path(f, root)]
    info = {"test_files": len(test_files), "by_language": {}, "frameworks": [], "command_hint": None}
    for f in test_files:
        lang = language_of(f) or "other"
        info["by_language"][lang] = info["by_language"].get(lang, 0) + 1
    py_tests = [f for f in test_files if f.endswith((".py", ".pyi"))]
    if py_tests:
        uses_unittest = any(
            "unittest" in read_text(os.path.join(root, f)) for f in py_tests
        )
        has_pytest_cfg = any(
            os.path.isfile(os.path.join(root, n)) for n in ("pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini")
        )
        if uses_unittest and not has_pytest_cfg:
            info["frameworks"].append("unittest (unittest.TestCase found, no pytest config)")
        else:
            info["frameworks"].append("pytest (assumed: python test files found)")
    if "JavaScript" in info["by_language"] or "TypeScript" in info["by_language"]:
        pkg = os.path.join(root, "package.json")
        if os.path.isfile(pkg):
            try:
                deps = json.loads(read_text(pkg))
            except (OSError, ValueError):
                deps = {}
            merged = {**deps.get("dependencies", {}), **deps.get("devDependencies", {})}
            for fw in ("vitest", "jest", "mocha", "ava", "tap"):
                if fw in merged:
                    info["frameworks"].append(f"{fw} (package.json)")
    if os.path.isfile(os.path.join(root, "Cargo.toml")):
        info["frameworks"].append("cargo test")
    if os.path.isfile(os.path.join(root, "go.mod")):
        info["frameworks"].append("go test ./...")
    return info


def git_state(root: str) -> dict | None:
    """Report the working tree state when git is available.

    Used by the detective to protect edits the user already made: any file
    listed here as modified is theirs, not ours.
    """
    if not os.path.isdir(os.path.join(root, ".git")):
        return None
    try:
        def run(*args: str) -> str:
            return subprocess.run(
                ["git", *args], cwd=root, capture_output=True, text=True, timeout=15
            ).stdout.strip()

        status = run("status", "--porcelain")
        branch = run("rev-parse", "--abbrev-ref", "HEAD")
        head = run("rev-parse", "--short", "HEAD")
        recent = run("log", "--oneline", "-5")
    except (OSError, subprocess.SubprocessError):
        return {"available": False, "note": "git binary not runnable in this environment"}
    modified, untracked = [], []
    for line in status.splitlines():
        code, _, path = line[:2], line[2:3], line[3:]
        path = path.strip().strip('"')
        (untracked if code.strip() == "??" else modified).append(path)
    return {
        "available": True,
        "branch": branch,
        "head": head,
        "modified": modified,
        "untracked": untracked,
        "recent_commits": recent.splitlines() if recent else [],
        "note": "modified/untracked files are pre-existing user work: do not revert or reformat",
    }


def folder_layout(root: str, files: list[str], depth: int) -> dict:
    tree: dict = defaultdict(lambda: {"files": 0, "languages": Counter(), "tests": 0})
    for rel in files:
        if rel.count("/") == 0:
            key = "(root)"
        else:
            key = "/".join(rel.split("/")[:-1][:depth])
        lang = language_of(rel)
        tree[key]["files"] += 1
        if lang:
            tree[key]["languages"][lang] += 1
        if is_test_path(rel, root):
            tree[key]["tests"] += 1
    return {
        k: {
            "files": v["files"],
            "tests": v["tests"],
            "languages": dict(v["languages"].most_common(5)),
        }
        for k, v in sorted(tree.items(), key=lambda kv: -kv[1]["files"])
    }


def scan(root: str, scope: str | None, depth: int) -> dict:
    root = os.path.abspath(root)
    if scope:
        base = os.path.join(root, scope)
        root_for_walk = base if os.path.isdir(base) else root
    else:
        root_for_walk = root
    files = list(iter_files(root_for_walk))
    if root_for_walk != root:
        files = [os.path.relpath(os.path.join(root_for_walk, f), root).replace(os.sep, "/") for f in files]

    languages: Counter = Counter()
    loc = 0
    generated: list[str] = []
    for rel in files:
        lang = language_of(rel)
        if not lang:
            continue
        languages[lang] += 1
        full = os.path.join(root, rel)
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as fh:
                loc += sum(1 for _ in fh)
        except OSError:
            continue
        if is_generated(full):
            generated.append(rel)

    manifests = []
    for rel in files:
        base = os.path.basename(rel)
        if base in MANIFESTS or base in ("Makefile", "README.md", "opencode.json", "opencode.jsonc", "AGENTS.md", "CLAUDE.md"):
            manifests.append({"file": rel, "ecosystem": MANIFESTS.get(base, "meta")})

    tests = detect_tests(root, files)
    test_probe = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_probe.py")
    if tests["test_files"] and os.path.isfile(test_probe):
        tests["command_hint"] = f'python3 {os.path.relpath(test_probe, os.getcwd())} --root {root} --run'

    return {
        "root": root,
        "scanned_files": len(files),
        "source_files": sum(languages.values()),
        "approx_lines_of_code": loc,
        "languages": dict(languages.most_common()),
        "primary_language": languages.most_common(1)[0][0] if languages else None,
        "layout": folder_layout(root, files, depth),
        "manifests": manifests,
        "entry_points": detect_entry_points(root, files),
        "tests": tests,
        "generated_files": generated[:20],
        "generated_note": "do not edit by hand; fix the generator instead" if generated else None,
        "git": git_state(root),
        "files": files if len(files) <= 400 else files[:400] + [f"... {len(files) - 400} more"],
    }


def render(d: dict) -> str:
    out = []
    out.append(f"PROJECT MAP  {d['root']}")
    out.append("=" * 72)
    out.append(f"files scanned : {d['scanned_files']}  (source: {d['source_files']}, ~{d['approx_lines_of_code']} lines)")
    out.append(f"primary lang  : {d['primary_language'] or 'unknown'}")
    if d["languages"]:
        out.append("languages     : " + ", ".join(f"{k}={v}" for k, v in list(d["languages"].items())[:8]))
    out.append("")
    out.append("LAYOUT (largest areas)")
    for name, info in list(d["layout"].items())[:20]:
        langs = ", ".join(f"{k}:{v}" for k, v in info["languages"].items()) or "-"
        out.append(f"  {name:<45} {info['files']:>5} files  tests={info['tests']:<4} {langs}")
    out.append("")
    out.append("MANIFESTS / META")
    for m in d["manifests"]:
        out.append(f"  {m['file']:<50} [{m['ecosystem']}]")
    out.append("")
    out.append("ENTRY POINTS")
    for e in d["entry_points"]:
        out.append(f"  {e['kind']:<20} {e['name']:<28} {e['location']}")
    if not d["entry_points"]:
        out.append("  (none detected)")
    out.append("")
    out.append("TESTS")
    out.append(f"  test files : {d['tests']['test_files']}")
    out.append(f"  frameworks : {', '.join(d['tests']['frameworks']) or '(none detected)'}")
    if d["tests"]["command_hint"]:
        out.append(f"  run with   : {d['tests']['command_hint']}")
    out.append("")
    if d["generated_files"]:
        out.append("GENERATED (do not hand-edit)")
        for g in d["generated_files"]:
            out.append(f"  {g}")
        out.append("")
    g = d["git"]
    if g and g.get("available"):
        out.append("WORKING TREE (pre-existing user work - preserve)")
        out.append(f"  branch {g['branch']} @ {g['head']}")
        for p in g["modified"][:20]:
            out.append(f"  M {p}")
        for p in g["untracked"][:20]:
            out.append(f"  ? {p}")
        out.append("")
    elif g and not g.get("available"):
        out.append(f"WORKING TREE\n  unavailable: {g.get('note')}")
        out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Map a project before investigating it.")
    ap.add_argument("--root", default=".", help="project root (default: .)")
    ap.add_argument("--dir", help="scope the scan to a subdirectory")
    ap.add_argument("--depth", type=int, default=1, help="folder layout depth")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()

    data = scan(args.root, args.dir, args.depth)
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(truncate(render(data), 12000))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())