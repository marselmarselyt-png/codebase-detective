# Investigation workflow — phase by phase

The eight phases from `SKILL.md`, expanded. Read this when a phase does not
obviously apply to your situation.

---

## Phase 1 — Scan

```bash
python3 scripts/map_project.py --root . --json > /tmp/map.json
```

What to extract before touching anything:

| Question | Where the answer is |
|----------|--------------------|
| What language(s)? | `languages`, `primary_language` |
| Where does execution start? | `entry_points` |
| Where are the tests and what runs them? | `tests.frameworks`, `tests.command_hint` |
| Which directories are noise? | `SKIP_DIRS` in `scripts/_common.py`; extend via the ignore list |
| What is generated and must not be hand-edited? | `generated_files` |
| What has the user already changed? | `git.modified`, `git.untracked` |

**Bounding the scan in a large repository.** Do not map a million-line monorepo
to find one failing endpoint.

1. Start at the entry point named in the report.
2. Walk *down* one hop with `trace_symbol.py --file`.
3. Widen only when the trace leaves the area you started with.

Map breadth is not a virtue. Evidence is.

## Phase 2 — Map dependencies

```bash
python3 scripts/impact.py --root . --list
```

Read the hotspot list first. A file imported by forty modules is where changes
cause outages; a leaf module is where changes are cheap.

Record: the hotspot ranking, the public surfaces (`__init__.py`, `index.*`,
`api` packages, published crate/SDK entry points), and anything with no inbound
edges that should have some (usually dynamic wiring — a smell worth reporting).

## Phase 3 — Investigate

### How to read a stack trace

Read it **bottom-up for the origin**, top-down for the symptom. The deepest
frame in your own code is where the bad value entered the system. Frames above
it are propagation.

### Tracing from a value instead of a symbol

When the log gives you a value rather than a function name (`tier_used:
"STANDARD"`), start from the *producer* of that value:

```bash
python3 scripts/trace_symbol.py --root . --symbol tier_used       # the key name
grep -rn "STANDARD" src/                                        # the constant
```

Then ask, for each hop: *what produced this value, and what did the producer
believe it was?* The bug is almost always a **contract disagreement** between a
producer and a consumer, not a typo in the consumer.

### Hypothesis discipline

Keep a table while you work:

| Hypothesis | Evidence for | Evidence against | Status |
|-----------|--------------|------------------|--------|
| | | | OPEN / REJECTED / CONFIRMED |

A hypothesis with no evidence against is not confirmed; it is untested.

## Phase 4 — Impact

```bash
python3 scripts/impact.py --root . --files src/a.py src/b.py --symbols change_me
```

Answer three questions in writing before you edit:

1. Who breaks if I change this? (list the files, not "the system")
2. What would catch a mistake? (list the tests, or state that none exist)
3. What am I unable to see? (runtime config, external consumers, DB)

If the answer to (3) contains anything load-bearing, that belongs in the
report's risk section *before* the edit.

## Phase 5 — Plan

The plan is a paragraph and a diff sketch. Keep it in the conversation, not in
the files. Criteria for a good plan:

- Fixes the cause, not the symptom.
- Touches the fewest files that can own the fix.
- Preserves behaviour that is not broken (including deliberate fallbacks).
- Has a test that fails before and passes after.
- Does not bundle a refactor.

## Phase 6 — Edit

```bash
python3 scripts/snapshot.py --root . --save <files you will touch>
```

Rules that prevent the most common damage:

- One concern per edit. If you spotted another bug, report it; do not fix it in
  the same pass.
- Never reformat lines you are not changing.
- Never "clean up" a workaround you do not understand — it may be load-bearing.
- Keep the existing style exactly: naming, comment language, error handling.

Afterwards:

```bash
python3 scripts/snapshot.py --root . --verify
```

Anything in `changed_since_snapshot` that you did not intend to touch must be
inspected immediately.

## Phase 7 — Verify

```bash
# 1. does a test actually reproduce the bug?
python3 scripts/test_probe.py --root . --run --cmd "<narrowest reproducing command>"

# 2. whole suite
python3 scripts/test_probe.py --root . --run

# 3. compare against the pre-change state
python3 scripts/test_probe.py --root . --run --baseline /tmp/before.json   # BEFORE editing
python3 scripts/test_probe.py --root . --run --compare /tmp/before.json   # AFTER editing
```

When the suite was already red, `--baseline` is what separates your change from
pre-existing breakage. Without it you cannot honestly claim "no new failures".

If nothing fails before your fix, you have not found the bug yet — or the bug
has no coverage. Both are findings; report them.

## Phase 8 — Report

Fill `templates/report.md`. The two fields that carry the most weight:

- **Root cause** — `file:line` plus the mechanism. Not a restatement of the
  symptom.
- **Verification** — the literal command and the literal exit code. If you
  could not run it, write `NOT RUN` and explain why.