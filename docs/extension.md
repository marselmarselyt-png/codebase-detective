# Visual Studio Code extension for debugging AI agents

No. Read the rest.

This is an investigation skill, not an editor. The distinction matters, and the
skill is built around it.

## What the agent used to do

An agent gets a stack trace. Within about thirty seconds it forms a hypothesis,
opens a file, and edits. The edit is usually plausible. Sometimes it is correct.

The problem is that the transcript looks identical either way. There is no way
to tell, after the fact, whether the agent:

- understood the system, or guessed from the top of the stack trace;
- checked what else depends on the code it changed, or hoped;
- ran the tests, or believed the change was obviously fine.

That ambiguity is the actual failure mode. Not wrong code — *unfalsifiable*
code. A confident summary reads exactly like a correct one, so nobody catches
it until the bug comes back in production.

## What this inverts

The workflow runs in the opposite order, and every phase leaves an artifact:

```
Scan -> Map dependencies -> Investigate -> Assess risk
      -> Plan -> Edit -> Run tests -> Report
```

Three properties make the result checkable:

**Investigation precedes editing, structurally.** The agent may not modify code
until it has written down a root cause with a `file:line` citation and an impact
assessment. Editing is the last step of the analysis, not the first move.

**Claims are anchored.** A diagnosis without a code citation is not a
conclusion, it is a hypothesis, and it gets labelled as one. You can open any
file and check whether the cited line says what the report claims it says.

**Verification is an exit code, not a sentiment.** The skill ships
`test_probe.py`, which runs the project's real test command and reports the
actual exit code. It cannot report `PASS` without `exit 0`. When no test
framework exists, the honest answer is `NOT RUN` — and the report says so.

## The failure mode this actually prevents

Consider a real bug in the bundled fixture: customers lose their discount.

The pricing module is fine. The unit tests for it are green. The bug lives in the
transport layer, where the request field is read under a name the API contract
does not define, so the tier arrives as `null` and is normalised to the default
before anyone prices the order.

An agent that reads the stack trace sees a pricing error. It fixes pricing. The
tests pass. The discount is still gone.

This skill's agent traces the *value* upstream instead: from where the tier
enters, to what the contract says it is called, to where the mismatch occurs. The
root cause is one line in one file, and it is cited. The regression test written
for it rejects the obvious wrong fix.

## Confidence is a first-class output

The report ends with a level — `HIGH`, `MEDIUM`, `LOW`, or `CAUSE NOT FOUND` —
and the justification for it. `CAUSE NOT FOUND` is a legitimate, valuable
result: the hypothesis table, the ruled-out candidates with the evidence that
eliminated them, and the next probe that would resolve it.

The eval suite scores this directly. Case 4 is an intermittent 502 with no log
line and nothing in the application logs. An agent that produces a confident
root cause there has failed the skill, regardless of how reasonable the cause
sounds. Shipping a plausible fix built on a guess costs a debugging cycle and
teaches everyone that the reports are unreliable.

## Where it stops

Static analysis cannot see runtime wiring, dependency injection, reflection,
configuration values, database contents, or consumers outside the repository.
The skill says this out loud in every report rather than implying coverage it
does not have.

It also cannot tell you whether your root cause is correct. That remains a human
call, which is why `tests/BUGS.md` exists and why the eval scoring rubric splits
mechanical checks from judgement.

## Try it against a real bug

Full walkthrough with real terminal output:
**[getting-started.md](getting-started.md)**

In short:

```bash
# 1. install
git clone https://github.com/marselmarselyt-png/codebase-detective.git \
  ~/.config/opencode/skills/codebase-detective

# 2. restart opencode

# 3. practise on the bundled broken project
cd ~/.config/opencode/skills/codebase-detective
python3 scripts/map_project.py  --root tests/fixture_repo
python3 scripts/trace_symbol.py --root tests/fixture_repo --symbol TIER_FIELD

# 4. run it on your own code: open your project and ask for an investigation
```

The tools work standalone too:

```bash
python3 scripts/map_project.py  --root .
python3 scripts/trace_symbol.py --root . --symbol <symbol-from-the-log>
python3 scripts/impact.py       --root . --files <files-you-plan-to-edit>
python3 scripts/test_probe.py   --root . --run
```

## Licence

MIT. See [LICENSE](LICENSE).
