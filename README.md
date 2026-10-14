# Codebase Detective

> **Investigate First. Modify Later.**

An AI agent skill that behaves like a software detective instead of a
guess-driven code editor. It maps an unfamiliar repository, traces root causes
across files, analyses the blast radius of a change, runs the tests that
actually exist, and reports what it knows — and what it does not.

Built for opencode, Claude Code, and any other agent that can load a
`SKILL.md`.

---

## The problem

Coding agents fail in a predictable way: they see a stack trace, form a
hypothesis in the first thirty seconds, and start editing. The edit is usually
plausible. Sometimes it is even correct. But nothing in the transcript tells you
whether the agent understood the system, whether the change breaks something
else, or whether the tests were ever run.

Worse, the failure is invisible: a confident summary at the end reads exactly
like a correct one.

## The approach

Codebase Detective inverts the order of operations and makes the reasoning
auditable:

1. **No edit before investigation.** You may not modify code until you have
   written down a root-cause hypothesis with evidence and an impact assessment.
2. **Every diagnosis cites `file:line`.** A conclusion without a citation is
   labelled a guess.
3. **The user's work is protected.** Snapshot before editing, verify after, never
   revert what you did not write.
4. **Tests are run or not claimed.** Real command, real exit code. "Should pass"
   is not evidence.
5. **Uncertainty is reported.** `CAUSE NOT FOUND` with a hypothesis table is a
   valid, valuable outcome.
6. **Risky actions need approval.** Deleting files, changing public APIs,
   migrations, dependency bumps, disabling tests.

## Install

### opencode

```bash
git clone <this-repo> ~/.config/opencode/skills/codebase-detective
```

or copy the directory to `.opencode/skills/codebase-detective` in a project for
project-scoped use. Restart opencode to pick it up.

### Claude Code / agents.md-compatible runners

```bash
git clone <this-repo> ~/.claude/skills/codebase-detective
```

## Use

Ask for an investigation, or invoke the skill explicitly:

> "Gold customers stopped receiving their 5% discount. A `POST /checkout` with
> `"tier": "gold"` comes back as `STANDARD`. Investigate."

The skill then runs eight phases:

```
Scan project -> Map dependencies -> Investigate bug -> Analyse risk
             -> Plan the change  -> Edit code     -> Run tests -> Report
```

## What ships in the box

```
SKILL.md                   the rules and the workflow
scripts/
  map_project.py           phase 1 - project map, entry points, test setup
  impact.py                phases 2 & 4 - dependency graph, hotspots, blast radius
  trace_symbol.py          phase 3 - cross-file symbol and file tracing
  snapshot.py              guards the user's pre-existing changes
  test_probe.py            phase 7 - real test discovery, real exit codes, baselines
references/
  workflow.md              each phase in detail
  patterns.md              cross-file root cause catalogue (7 patterns + anti-patterns)
  evidence.md              evidence standards and the confidence rubric
  testing.md               test discovery per stack, honest reporting
  impact.md                risk tiers and review checklists
templates/
  report.md                the investigation report deliverable
tests/
  test_detective.py        31 tests covering every script, incl. fix-and-verify
  fixture_repo/            a deliberately broken project (3 planted bugs)
  BUGS.md                  grader's ground truth
evals/
  RUN.md                   how to test the skill on a real agent
  run_evals.sh             harness: 5 cases, stages a clean fixture, scores the run
  score_report.py          scores a report against the skill's rules
  score_transcript.py      scores what the agent did, in order
```

All scripts are **Python 3 standard library only**. No pip install, no node
install. They run inside any target repository without touching it.

## Try the tools on the broken fixture

```bash
git clone <this-repo> && cd codebase-detective

python3 scripts/map_project.py --root tests/fixture_repo
python3 scripts/trace_symbol.py --root tests/fixture_repo --symbol Customer
python3 scripts/impact.py --root tests/fixture_repo --files shopcart/api.py
```

The fixture is a four-layer order pipeline with three planted bugs: a field name
that drifts between the HTTP contract and the parser, a mutable default argument
that leaks reservations between orders, and a boolean read as an object in
JavaScript. `tests/BUGS.md` has the ground truth.

## Run the tests

```bash
python3 -m unittest discover -s tests -t . -v
```

The suite verifies the tools against the fixture *and* applies the documented
fixes to a temporary copy, proving that the regression tests turn green — and
that a plausible-but-wrong fix does not.

## Evaluate the skill itself

Scripts being correct does not mean agents behave correctly. `evals/` runs five
scenarios against a real agent session and scores the transcript:

```bash
AGENT_CMD="opencode run --prompt-file -" ./evals/run_evals.sh
```

Case 4 is the important one: an intermittent failure with no available
evidence. The correct behaviour is to report `CAUSE NOT FOUND` with a hypothesis
table. An agent that invents a confident cause fails the skill even if it sounds
persuasive.

## Requirements

Python 3.9+. Nothing else. `node` is optional and only used by one JavaScript
test.

## License

MIT — see [LICENSE](LICENSE).