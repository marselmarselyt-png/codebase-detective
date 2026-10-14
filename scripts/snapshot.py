#!/usr/bin/env python3
"""Protect the user's existing work before you edit anything.

--save     record a content hash of the files you are about to touch (and, with
           --all, of every tracked source file), so pre-existing modifications
           can be distinguished from yours.
--verify   re-hash the recorded files and report which ones changed since the
           snapshot. Anything unexpected must be inspected, not overwritten.
--show     show git working-tree state, when git is available: those modified
           and untracked files are the user's work.

Usage:
    python3 snapshot.py --root . --show
    python3 snapshot.py --root . --save src/pricing.py src/cart.py --out .detective-snapshot.json
    python3 snapshot.py --root . --verify --out .detective-snapshot.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import iter_files  # noqa: E402

SNAPSHOT_FILE = ".detective-snapshot.json"


def sha256(path: str) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def git_state(root: str) -> dict | None:
    if not os.path.isdir(os.path.join(root, ".git")):
        return None
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, timeout=15
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return {"available": False, "note": "git present but not runnable here"}
    mod, untracked = [], []
    for line in out.splitlines():
        code, path = line[:2], line[3:].strip().strip('"')
        (untracked if code.strip() == "??" else mod).append(path)
    return {"available": True, "modified": mod, "untracked": untracked}


def save(root: str, targets: list[str], out: str, take_all: bool) -> dict:
    files = list(iter_files(root)) if take_all else [t for t in targets]
    snap = {
        "root": root,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "scope": "all tracked source files" if take_all else ", ".join(targets) or "(none)",
        "git": git_state(root),
        "hashes": {f: sha256(os.path.join(root, f)) for f in files},
    }
    snap["hashes"] = {k: v for k, v in snap["hashes"].items() if v}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(snap, fh, indent=2)
    return snap


def verify(root: str, snapshot_path: str) -> dict:
    try:
        with open(snapshot_path, "r", encoding="utf-8") as fh:
            snap = json.load(fh)
    except (OSError, ValueError) as exc:
        return {"error": f"cannot read snapshot: {exc}"}

    changed, missing, untouched = [], [], []
    for f, h in snap.get("hashes", {}).items():
        now = sha256(os.path.join(root, f))
        if now is None:
            missing.append(f)
        elif now != h:
            changed.append(f)
        else:
            untouched.append(f)
    return {
        "snapshot": snapshot_path,
        "created": snap.get("created"),
        "scope": snap.get("scope"),
        "changed_since_snapshot": changed,
        "deleted_since_snapshot": missing,
        "unchanged_count": len(untouched),
        "pre_existing_user_changes": (snap.get("git") or {}).get("modified", []),
        "verdict": (
            "files changed since snapshot: " + ", ".join(changed)
            if changed
            else "no tracked file changed since the snapshot"
        ),
        "rule": (
            "every changed file must be one you intended to edit, with only the planned lines "
            "touched. Anything else means the user's work drifted - inspect the diff, do not revert silently."
        ),
    }


def render_show(state: dict | None, root: str) -> str:
    out = [f"PRE-EXISTING USER WORK in {root}", "=" * 72]
    if state is None:
        out.append("  no git repository here - snapshot hashes are the only baseline available")
    elif not state.get("available"):
        out.append(f"  git not runnable ({state.get('note')}) - fall back to hash snapshots")
    else:
        out.append("  MODIFIED (user edits in progress - never revert these):")
        out.extend(f"    M {p}" for p in state["modified"] or ["(clean)"])
        out.append("  UNTRACKED (new user files - never delete these):")
        out.extend(f"    ? {p}" for p in state["untracked"] or ["(none)"])
    out.append("")
    out.append("Snapshot before editing: python3 snapshot.py --root . --save <files>")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Snapshot and verify user files before/after editing.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--save", nargs="*", default=None, metavar="FILE")
    ap.add_argument("--all", action="store_true", help="with --save: hash every tracked source file")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    out = args.out or os.path.join(root, SNAPSHOT_FILE)

    if args.verify:
        res = verify(root, out)
        print(json.dumps(res, indent=2) if args.json else
              "\n".join(f"{k}: {v}" for k, v in res.items() if not isinstance(v, (list, dict)))
              + ("\nCHANGED:\n" + "\n".join(f"  {c}" for c in res.get("changed_since_snapshot", []))
                 if res.get("changed_since_snapshot") else ""))
        return 0 if not res.get("error") else 2

    if args.save is not None:
        snap = save(root, args.save, out, args.all)
        print(json.dumps(snap, indent=2) if args.json else
              f"snapshot saved: {out}\n  {len(snap['hashes'])} file(s) hashed\n  scope: {snap['scope']}")
        return 0

    state = git_state(root)
    print(json.dumps(state, indent=2) if args.json else render_show(state, root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())