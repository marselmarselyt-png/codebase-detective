# Getting started — step by step

Everything below is copy-pasteable and was verified against this repository.
Times are for a normal laptop.

---

## Step 0 — Check what you have

```bash
python3 --version        # needs 3.9 or newer
```

That is the only requirement. The scripts use the Python standard library only,
so there is nothing to `pip install`.

Optional, only for the JavaScript test:

```bash
node --version           # 18 or newer
```

---

## Step 1 — Install

### 1a. opencode, all projects (global)

```bash
git clone https://github.com/marselmarselyt-png/codebase-detective.git \
  ~/.config/opencode/skills/codebase-detective
```

### 1b. opencode, one project only

```bash
cd /path/to/your/project
git clone https://github.com/marselmarselyt-png/codebase-detective.git \
  .opencode/skills/codebase-detective
```

### 1c. Claude Code

```bash
git clone https://github.com/marselmarselyt-png/codebase-detective.git \
  ~/.claude/skills/codebase-detective
```

### 1d. No git? Download and unpack

Download the zip from the repo page, extract it, and rename the folder to
`codebase-detective` in the directory from 1a, 1b or 1c.

### 1e. Any other agent

Point the agent at `SKILL.md`. The skill is one Markdown file with YAML
frontmatter (`name`, `description`) — anything that can read a Markdown file can
use it.

---

## Step 2 — Restart and verify

**Restart opencode.** Skill files are read at startup; a running session keeps
using the old configuration.

Then confirm it loaded. Ask the agent:

```
What skills are available?
```

You should see `codebase-detective` listed. Or check the filesystem directly:

```bash
ls ~/.config/opencode/skills/codebase-detective/SKILL.md
```

If the skill is not listed, see [Troubleshooting](#troubleshooting).

---

## Step 3 — First run: on a project that is deliberately broken

The repository ships a fixture with three planted bugs. Practise on it before
pointing the skill at real code.

```bash
cd ~/.config/opencode/skills/codebase-detective
```

### 3a. Map the project

```bash
python3 scripts/map_project.py --root tests/fixture_repo
```

Real output:

```
PROJECT MAP  .../tests/fixture_repo
========================================================================
files scanned : 17  (source: 14, ~380 lines)
primary lang  : Python
languages     : Python=11, JavaScript=3

LAYOUT (largest areas)
  shopcart      7 files  tests=0    Python:7
  tests         4 files  tests=4    Python:4
  web           4 files  tests=1    JavaScript:3

TESTS
  test files : 5
  frameworks : unittest (unittest.TestCase found, no pytest config)
```

### 3b. Run the fixture's tests — they fail, and that is the point

```bash
python3 scripts/test_probe.py --root tests/fixture_repo --run \
  --cmd "python3 -m unittest discover -s tests -t ."
```

Real output:

```
COMMAND   : python3 -m unittest discover -s tests -t .
EXIT CODE : 1
STATUS    : FAIL   (0.77s)
FAILURE LINES (verbatim from output):
  FAIL: test_documented_payload_field_is_honoured (tests.test_regression_tier...)
  AssertionError: 'STANDARD' != 'GOLD'
```

`test_pricing_unit.py` is **green** while the product is broken — the classic
cross-file bug. Notice that the tool reported the real exit code, not a guess.

### 3c. Trace the value across files

```bash
python3 scripts/trace_symbol.py --root tests/fixture_repo --symbol TIER_FIELD
```

Real output:

```
SYMBOL TRACE: TIER_FIELD
DEFINITIONS (1)
  shopcart/api.py:9  TIER_FIELD = "customerTier"
REFERENCES (1)
  shopcart/api.py:21  tier=customer.get(TIER_FIELD),
```

Now read `tests/fixture_repo/docs/api.md`: the documented field is `tier`. The
parser reads `customerTier`. **That mismatch is the root cause** — everything
downstream normalises the missing value to `STANDARD`, and `pricing.py` applies
a 0% rate.

### 3d. Check the blast radius before editing

```bash
python3 scripts/impact.py --root tests/fixture_repo --files shopcart/api.py
```

Real output:

```
IMPACT ANALYSIS  risk=MEDIUM
RISK REASONS
  - 1 test(s) reference the changed code directly
DEPENDENTS: 1 total, 0 production
  tests/test_regression_tier.py -> shopcart/api.py
TEST COVERAGE
  direct     : tests/test_regression_tier.py
```

### 3e. See the whole dependency graph

```bash
python3 scripts/impact.py --root tests/fixture_repo --list
```

```
HOTSPOTS (most-imported modules - editing these is high risk)
  shopcart/pricing.py    imported_by=3
  shopcart/tiers.py      imported_by=3
  shopcart/models.py     imported_by=2
```

### 3f. Ground truth

```bash
cat tests/BUGS.md
```

All three planted bugs, with the exact evidence trail and the minimal correct
fix. Compare what you found against it.

---

## Step 4 — First run: on your own code

Open your project in opencode and ask for an investigation. Plain language is
enough; no commands needed:

> Checkout is throwing a 500 since Tuesday. `POST /api/orders` fails but only
> for orders with more than three line items. Find out why and fix it.

The skill will walk the eight phases and end with a report. What a finished
investigation looks like is in
[`templates/example-report.md`](../templates/example-report.md).

### If the skill is not triggered

Agents load skills on relevance. If it did not activate, either the symptom is
too vague, or you can name it explicitly:

> Use the codebase-detective skill to investigate this.

---

## Step 5 — Run the test suite

```bash
cd ~/.config/opencode/skills/codebase-detective
python3 -m unittest discover -s tests -t . -v
```

```
Ran 38 tests in 35.3s

OK
```

What that actually proves:

| Test group | Guarantee |
|------------|-----------|
| `MapProjectTests` | mapping finds languages, layout, test setup |
| `ImpactTests` | dependency edges resolve, blast radius and risk tiers are ordered correctly, JS edges resolve |
| `TraceSymbolTests` | cross-file tracing works in Python and JavaScript, duplicates are flagged, quoted lines are verbatim |
| `TestProbeTests` | real exit codes, `PASS` only on exit 0, baselines detect new failures, missing toolchains report `NOT RUN` |
| `SnapshotTests` | user files are detected as changed, deleted files are reported |
| `FixtureRegressionTests` | the planted bugs reproduce, the documented fixes make the suite green, a plausible **wrong** fix is rejected, and the tools never write to the target repo |
| `StripCommentsTests` | a real regression: string contents used to be dropped from every quoted line |

---

## Step 6 — Evaluate the skill on an agent (optional)

Scripts being correct does not mean agents behave correctly.

```bash
AGENT_CMD="opencode run --prompt-file -" ./evals/run_evals.sh
```

Runs five scenarios against a real agent session, stages a clean copy of the
fixture for each, and scores the transcripts. Details in
[`evals/RUN.md`](../evals/RUN.md).

---

## Using the tools on their own

They are useful without the skill.

```bash
python3 scripts/map_project.py  --root . --json          # machine readable
python3 scripts/trace_symbol.py --root . --symbol NAME
python3 scripts/trace_symbol.py --root . --file src/api.py --importers
python3 scripts/impact.py       --root . --files a.py b.py --symbols change_me
python3 scripts/snapshot.py     --root . --show          # what have you changed?
python3 scripts/snapshot.py     --root . --save a.py b.py
python3 scripts/snapshot.py     --root . --verify
python3 scripts/test_probe.py   --root . --list
python3 scripts/test_probe.py   --root . --run --baseline before.json
python3 scripts/test_probe.py   --root . --run --compare  before.json
```

Add `--json` to any of them for structured output.

**The scripts never write to the repository they inspect.** A test asserts this
by hashing the fixture before and after a full run.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Skill not listed | opencode has not restarted | Quit and reopen opencode |
| Skill not listed (project install) | wrong folder name | The folder must be `codebase-detective` and contain `SKILL.md` |
| `Permission denied` on scripts | download lost the executable bit | `chmod +x scripts/*.py evals/*.py` |
| `python3: command not found` | Python missing | Install Python 3.9+ |
| `ModuleNotFoundError: pytest` | project uses pytest, you do not have it | `pip install pytest` |
| Tool says `NOT RUN` | no test framework detected | That is the honest answer; check `test_probe.py --list` |
| Skill answers without investigating | symptom too vague | Name the failing endpoint, module, or symbol |

---

## Uninstall

```bash
rm -rf ~/.config/opencode/skills/codebase-detective
```

Nothing is written to your projects, so there is nothing else to clean up.
