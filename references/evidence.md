# Evidence standards and honest reporting

The value of this skill is that its conclusions can be trusted. That property
comes entirely from the rules below.

---

## What counts as evidence

| Tier | Example | Strength |
|------|---------|----------|
| **Runtime** | Log line, stack frame, failing assertion, profiler output, DB row | Strongest — shows the system as it actually ran |
| **Executable test** | A test that fails on the unfixed tree and passes on the fixed one | Strong — reproducible, falsifiable |
| **Code fact** | `file:line` showing a value's origin, a contract, a branch | Strong for structure, silent about runtime |
| **Documentation** | API spec, README, changelog, ticket | Strong for intent; may lag reality |
| **History** | `git log -S`, `git blame`, the commit that introduced the line | Strong for "when", needs a runtime check for "why" |
| **Inference** | "this probably causes that" | **Not evidence.** Label it a hypothesis. |

A conclusion is defensible when it is supported by at least one runtime or
executable-test fact, or when it is a structural claim cited to `file:line` and
explicitly marked as static.

## Citation format

```
shopcart/api.py:11        TIER_FIELD = "customerTier"
shopcart/tiers.py:31      if raw is None: return "STANDARD"
tests/test_regression_tier.py:27   self.assertEqual(result["tier_used"], "GOLD")
```

Quote the line. A citation that makes the reader open the file to check whether
it says what you claim is a weak citation.

## Separating observation, inference, action

Write these three in different registers:

- **Observation** — "the suite exits 1; four assertions in `test_regression_tier.py` fail".
- **Inference** — "the tier field never reaches the domain model, so
  `normalize(None)` yields `STANDARD`".
- **Action** — "change `TIER_FIELD` to `tier`; re-run; compare to baseline".

Never let an inference borrow the authority of an observation. The most common
failure mode of a confident agent is stating an inference in the grammar of a
fact.

## Confidence rubric

| Level | Requires |
|-------|----------|
| **HIGH** | Reproduced before the change; root cause cited to `file:line`; a test fails before and passes after; full suite run with exit code 0; blast radius reviewed |
| **MEDIUM** | Code path proven statically with citations; change applied; tests run but do not cover this exact path; some runtime verification (a log, a manual reproduction) |
| **LOW** | Plausible mechanism, partial evidence, inconclusive or absent test signal; the report must name what is missing |
| **CAUSE NOT FOUND** | No defensible cause. Required: the hypothesis table, what was ruled out, and the next probes |

Confidence is about *evidence*, not about effort or optimism. A tidy fix you
cannot verify is LOW, and saying so is correct behaviour.

## Phrasing

Use these:

- "Reproduced: `<command>` exits 1 with `<message>`."
- "Hypothesis (unconfirmed): the tier field is read under a different name at `api.py:11`."
- "Not verified in CI; only the local suite was run."
- "Cause not found. Ruled out: <hypothesis> (evidence). Next probe: <action>."
- "Baseline before the change was already red (2 failures); after the change the same 2 failures remain and no new ones appeared."

Avoid these:

- "Should be fixed now." — unverified claim.
- "Tests pass." — unless you ran them and you show the exit code.
- "This is clearly the bug." — "clearly" is not evidence.
- "I couldn't run the tests, but the change looks correct." — state `NOT RUN`
  and stop making claims about verification.
- "I fixed a related issue too." — unrequested scope creep; report it instead.

## When the answer is "I don't know"

This is a first-class outcome, and reporting it well is a skill of its own:

1. State what you observed (with evidence).
2. List the hypotheses you tested and how each was eliminated.
3. State the remaining candidates in order of likelihood, with what would
   confirm each.
4. Say what you need (a log level change, a repro, access to an environment,
   permission to instrument the code) and ask for it.
5. Change nothing, or change only what is provably safe and reversible.

An honest `CAUSE NOT FOUND` with a strong hypothesis table is worth more than a
confident wrong fix, because a wrong fix costs a debugging cycle and destroys
the reporter's trust in every future report.

## Pressure situations

| Situation | Correct action |
|-----------|----------------|
| "Just make the error go away" | State what you know, what you do not, and what a guess would cost. Offer the smallest reversible change only with approval. |
| Deadline pressure | Ship a narrow, verified, reversible change; report the residual risk explicitly. Do not widen the diff. |
| Tests are broken on `main` | Baseline first. Never attribute pre-existing failures to your change, and never hide them. |
| The fix requires touching many files | That is a signal you have found a root cause, not a permission to refactor. Propose the layered fix, get approval. |