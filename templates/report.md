# Investigation Report: <one-line title>

> Fill every section. `UNKNOWN` is an acceptable answer; a fabricated one is not.
> Delete no section - a missing section is the most common way a report becomes
> misleading.

**Case ID**: <date>-<short-slug>
**Investigated by**: <agent / human>
**Repository state**: branch `<branch>` @ `<commit>` | uncommitted changes: `<yes/no>`
**Verdict**: `ROOT CAUSE FOUND` | `CAUSE NOT FOUND`
**Confidence**: `HIGH` | `MEDIUM` | `LOW`

---

## 1. Symptom

What was observed, in the reporter's words, plus the exact reproduction:

```
<command or request that shows the wrong behaviour>
```

**Expected**: <what should have happened>
**Actual**: <what happened>

## 2. Scope

- Area touched: <modules / packages>
- First bad version: `<commit/tag/unknown>`
- Reproducible: `YES (command)` | `INTERMITTENT (rate)` | `NOT YET REPRODUCED`

## 3. Evidence

Every row is an observation, not a conclusion.

| # | Observation | Source |
|---|-------------|--------|
| E1 | <what was seen> | `<file>:<line>` / `<test>:<test>` / `<log line>` |
| E2 | | |

Commands actually executed, with real exit codes:

```
$ <command>
exit code: <n>
```

## 4. Root cause

**Cause**: <the specific defect, in one sentence>
**Location**: `<file>:<line>`
**Mechanism**: <how the wrong value/flow reaches the symptom, step by step>
**Owner**: <which layer should own the fix, and why that layer>

Ruled out (each with the evidence that eliminated it):

| Hypothesis | Eliminated by |
|-----------|---------------|
| <candidate> | <evidence> |

## 5. Impact before change

```
risk: <LOW|MEDIUM|HIGH|CRITICAL>
```

- Production dependents: <n> (`<file>` …)
- Tests covering this path: <list or NONE>
- Public API / exported symbols affected: <list>
- Not visible to static analysis: <runtime wiring, external callers, DB…>

**Risky action required?** `NO` | `YES - <what>, approved by <who>`

## 6. Change made

Minimal diff only. No refactors, no drive-by formatting.

| File | Lines | What changed | Why here |
|------|-------|--------------|----------|
| `<file>` | `<a-b>` | <change> | <reason> |

**Not changed on purpose**: <known issues left alone, and where they are reported>

## 7. Verification

Baseline before the change:

```
$ <command>
exit code: <n>   -> <n> failed, <n> passed
```

After the change:

```
$ <command>
exit code: <n>   -> <n> failed, <n> passed
```

| Check | Result | Evidence |
|-------|--------|----------|
| Failing test that reproduces the bug | `NOW PASSES` / `STILL FAILS` | `<test id>` |
| Full suite | `PASS (exit 0)` / `FAIL (exit n)` / `NOT RUN` | output above |
| Manual check | `DONE` / `NOT DONE` / `IMPOSSIBLE - <why>` | |
| Performance / lint / type check | `<tool> exit <n>` | |

Tests added by this investigation: `<file>:<test>` (fails on the unfixed tree: `YES/NO`)

## 8. Remaining risks and follow-ups

| Risk | Likelihood | Impact | Mitigation / owner |
|------|-----------|--------|--------------------|
| <e.g. field renamed elsewhere> | LOW | MEDIUM | <who checks> |

**Not verified**: <paths, environments, or platforms that were not exercised>

## 9. Next steps

1. <action> — <owner>
2. <action> — <owner>

---

### Confidence justification

<Why this is HIGH/MEDIUM/LOW, and exactly what would move it up or down. If
LOW or CAUSE NOT FOUND, state the next probes that would resolve it.>