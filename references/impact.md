# Impact analysis

```bash
python3 scripts/impact.py --root . --list                          # phase 2: the map
python3 scripts/impact.py --root . --files a.py b.py --symbols x  # phase 4: the blast radius
```

---

## What static analysis can and cannot see

**Can see**: import and require edges, inheritance, exported symbols, test files
that import the code, file-level coupling, generated code.

**Cannot see** (say so in the report):

- Runtime wiring: dependency injection containers, service locators, plugin
  registries, decorators, reflection, `eval`, string-keyed handlers.
- Configuration: which environment variables or feature flags are set, and what
  the values are in the failing environment.
- Data: what is actually stored in the database, what shapes arrive over the
  network in production.
- Time and order: anything that depends on scheduling, concurrency, or clock.
- Everything outside this repository: other services, mobile clients, scripts,
  users of a published SDK.

A tool-generated risk tier is a floor, not a verdict. A change to a leaf helper
that reads an environment variable used by ten services is CRITICAL.

## Risk tiers

| Tier | Meaning | Required action |
|------|---------|-----------------|
| **LOW** | Leaf module, nothing imports it, no behaviour change | Edit, run tests, report |
| **MEDIUM** | A few direct dependents, or an exported symbol changes shape | Edit, run tests, check each dependent by reading the call site |
| **HIGH** | Many dependents, a package entry point, or a shared contract | Run the full suite, review each dependent's expectations, prefer a backward-compatible change |
| **CRITICAL** | Deep dependents, no test coverage, cross-repo consumers | Get approval before editing; add tests first; stage the rollout |

The tool raises the tier when no test covers the path — untested and widely
depended-on code is the worst combination in a codebase.

## Choosing *where* to fix

| Option | When it is right | When it is wrong |
|--------|------------------|------------------|
| Fix the producer | The value is wrong at the boundary (parsing, mapping, config) — the default | The producer is a shared service with many correct callers |
| Fix the consumer defensively | The producer's contract legitimately allows this value | It hides the producer bug and leaves every other consumer broken |
| Fix the shared layer | Both sides are wrong relative to the documented contract | There is no documented contract — write one first |
| Fix the caller of the caller | The bug was introduced by an adapter | Never for a one-off; it re-scatters the logic |

Prefer the layer that **owns the contract**. If the documentation, the producer,
and the consumer disagree, the documentation wins; fix the code to match it and
open an issue if the documentation is wrong.

## Minimising a diff

1. One concern per change.
2. No reformatting of surrounding lines.
3. No renames "while you are there".
4. No new abstraction for a single call site.
5. Keep the existing error-handling idiom (throw vs return-error vs raise-vs-
   return a sentinel) even if you dislike it.
6. If the correct fix is large, deliver the small safe part and report the rest
   as follow-up work.

## Review checklist before declaring done

- [ ] Every file I edited was in the impact list I ran before editing.
- [ ] Every exported symbol I touched still behaves as documented.
- [ ] Each direct dependent's call site was read, not assumed.
- [ ] Tests covering the path were run before and after.
- [ ] Pre-existing user modifications were preserved (`snapshot.py --verify`).
- [ ] Anything unverifiable is written into the report's risk section.
- [ ] Risky actions had explicit approval.

## Regression signals to look for

| Signal | Likely cause |
|--------|--------------|
| A test that only fails in the full suite, not in isolation | Shared state, test-order dependency, leaked global |
| A test that fails only when a new test runs first | New test polluted module-level state |
| Timing-dependent flakiness after the change | Removed a synchronisation, or introduced a race |
| A different test passing that used to fail | Your change altered behaviour another test depended on (good — check it is intended) |
| Everything passes but the bug remains | You fixed the wrong layer; re-trace from the symptom |