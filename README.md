# Codebase Detective

> **Investigate First. Modify Later.**

An AI agent skill that behaves like a software detective instead of a
guess-driven code editor. It maps an unfamiliar repository, traces root causes
across files, analyses the blast radius of a change, runs the tests that
actually exist, and reports what it knows — and what it does not.

Works with opencode, Claude Code, and any agent that can load a `SKILL.md`.
Python 3 standard library only — no `pip install`, nothing added to your repo.

---

## Why this exists

Coding agents fail in a predictable way: they see a stack trace, form a
hypothesis within thirty seconds, and start editing. The edit is usually
plausible. Sometimes it is even correct. But nothing in the transcript shows
whether the agent understood the system, whether the change breaks something
else, or whether the tests were ever run — and the failure is invisible, because
a confident summary reads exactly like a correct one.

This skill inverts the order of operations and makes the reasoning auditable.

## The six rules

| # | Rule |
|---|------|
| 1 | **No edit before investigation.** No code change until a root-cause hypothesis with evidence and an impact assessment exist. |
| 2 | **Every diagnosis cites `file:line`.** No citation means the claim is labelled a guess. |
| 3 | **The user's work is protected.** Snapshot before editing, verify after, never revert what you did not write. |
| 4 | **Tests are run or not claimed.** Real command, real exit code. "Should pass" is not evidence. |
| 5 | **Uncertainty is reported.** `CAUSE NOT FOUND` with a hypothesis table is a valid outcome. |
| 6 | **Risky actions need approval.** Deletions, public API changes, migrations, dependency bumps, disabling tests. |

## The eight phases

```
Scan project -> Map dependencies -> Investigate bug -> Analyse risk
             -> Plan the change  -> Edit code     -> Run tests -> Report
```

## Install

**opencode**

```bash
git clone https://github.com/marselmarselyt-png/codebase-detective.git \
  ~/.config/opencode/skills/codebase-detective
```

Or copy the folder to `.opencode/skills/codebase-detective` in a project for
project-scoped use. Restart opencode to load it.

**Claude Code**

```bash
git clone https://github.com/marselmarselyt-png/codebase-detective.git \
  ~/.claude/skills/codebase-detective
```

## Use

Ask for an investigation, or invoke the skill explicitly:

> "Gold customers stopped receiving their 5% discount. A `POST /checkout` with
> `"tier": "gold"` comes back as `STANDARD`. Investigate."

## What is in the box

```
SKILL.md                   rules + the 8-phase workflow the agent follows
scripts/
  map_project.py           phase 1 - languages, layout, entry points, test setup, dirty tree
  impact.py                phases 2 & 4 - dependency graph, hotspots, blast radius, risk tier
  trace_symbol.py          phase 3 - cross-file symbol and file tracing
  snapshot.py              guards your pre-existing changes (hash before, verify after)
  test_probe.py            phase 7 - real test discovery, real exit codes, baseline comparison
references/
  workflow.md              each phase in detail
  patterns.md              7 cross-file root cause patterns + the anti-patterns
  evidence.md              evidence standards, confidence rubric, phrasing
  testing.md               discovery per stack, honest reporting, anti-patterns
  impact.md                risk tiers, where to fix, review checklist
templates/
  report.md                the investigation report deliverable
  example-report.md        a filled-in example (scores 100% on the rubric)
tests/
  test_detective.py        31 tests over every script
  fixture_repo/            a deliberately broken project: 3 planted cross-file bugs
  BUGS.md                  ground truth for the planted bugs
evals/
  RUN.md                   how to test the skill on a real coding agent
  run_evals.sh             5 scenarios, staged automatically, then scored
  score_report.py          scores a report against the rules
  score_transcript.py      scores what the agent did, and in what order
```

## The tools

```bash
# what is this project, and what can I run?
python3 scripts/map_project.py --root .

# where does this symbol come from and who uses it?
python3 scripts/trace_symbol.py --root . --symbol apply_discount
python3 scripts/trace_symbol.py --root . --file src/checkout.ts --importers

# what breaks if I change these files?
python3 scripts/impact.py --root . --files src/pricing.py src/cart.py

# did the tests actually pass? (real exit code, never a guess)
python3 scripts/test_probe.py --root . --run --baseline before.json
python3 scripts/test_probe.py --root . --run --compare  before.json
```

All scripts read the target repository and never write to it. A test asserts
this by hashing the fixture before and after a full tool run.

## Try it on the broken fixture

```bash
git clone https://github.com/marselmarselyt-png/codebase-detective.git
cd codebase-detective
python3 scripts/map_project.py --root tests/fixture_repo
python3 scripts/trace_symbol.py --root tests/fixture_repo --symbol Customer
python3 scripts/impact.py --root tests/fixture_repo --files shopcart/api.py
```

The fixture is a four-layer order pipeline with three planted bugs:

1. A field name that drifts between the HTTP contract and the parser — the
   discount is silently lost, and a green unit suite hides it because the tests
   never enter the transport layer.
2. A mutable default argument that leaks reservations between unrelated orders.
3. A boolean read as an object in JavaScript, rejecting valid tokens.

`tests/BUGS.md` holds the ground truth.

## Run the tests

```bash
python3 -m unittest discover -s tests -t . -v
```

The suite covers every script and, crucially, applies the documented fixes to a
temporary copy of the fixture — proving the regression tests turn green **and**
that a plausible-but-wrong fix is rejected.

## Evaluate the skill itself

Scripts being correct does not mean agents behave correctly.

```bash
AGENT_CMD="opencode run --prompt-file -" ./evals/run_evals.sh
```

Case 4 is the one that matters: an intermittent failure with no available
evidence. The correct result is `CAUSE NOT FOUND` plus a hypothesis table. An
agent that invents a confident cause fails the skill even if it sounds
persuasive.

## Requirements

Python 3.9+. Nothing else. `node` is optional and used by one JavaScript test.

## Contributing

Open an issue describing a root-cause pattern the detective misses, or a case
where it edited before investigating. Bug reports about the tools themselves
welcome a failing test.

## License

MIT — see [LICENSE](LICENSE).