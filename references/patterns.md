# Cross-file root cause catalogue

Ordered by how often each one is the real answer. Each entry gives the
signature to look for, the files that usually hold it, and how to prove it.

---

## 1. Contract mismatch between producer and consumer

**Signature**: the value is *present and plausible* but wrong — wrong case,
wrong units, wrong nullability, wrong shape. Nothing crashes loudly.

| Variant | Typical symptom |
|---------|-----------------|
| Field name drift (`tier` vs `customerTier`) | Feature silently disabled |
| Unit drift (seconds vs milliseconds, cents vs euros, kg vs g) | Numbers off by a factor |
| Nullability drift (optional on one side, required on the other) | Default/fallback applied, real input ignored |
| Casing drift (`"Gold"` vs `"GOLD"`) | Key lookup misses, fallback path taken |
| Shape drift (tuple vs object, `bool` vs `{valid: bool}`) | Crash on property access, or always-falsy branch |
| Enum drift (numeric codes with different meanings per service) | Wildly wrong behaviour in one direction |

**Where it lives**: the producer that maps external input into the domain, and
the consumer that re-normalises defensively. Look for a *dict lookup with a
default* — `TABLE.get(value, FALLBACK)` is where a mismatch hides.

**Proof**: grep the wire contract (OpenAPI file, docs, a client SDK, a test
fixture) against the parsing code. If the documented field name and the read key
differ, you have the bug.

```bash
python3 scripts/trace_symbol.py --root . --symbol <the_field_name>
grep -rn "<documented_field>" docs/ *.yaml *.json src/
```

## 2. Duplicate logic that drifted

**Signature**: the same rule implemented in two places; a fix landed in one.

**Detection**: the same constant, condition, or magic number in several files.

```bash
python3 scripts/trace_symbol.py --root . --symbol <constant_or_helper>
```

If the trace shows a definition *and* a re-definition, that is the bug. If it
shows two independent implementations, decide which one is canonical before
editing anything.

**Proof**: delete neither. Change one, and demonstrate with a test that both
paths now agree.

## 3. Shared mutable state

**Signatures**:

- Mutable default argument: `def f(items=[])` (Python), `function f(arr = [])` (JS)
- Module-level singleton mutated by a "pure" function
- Global cache keyed by an input that is not part of the key
- Class attribute holding a list/dict

**Detection**:

```bash
grep -rn "def .*=\[\]\|def .*={}" --include=*.py src/
grep -rn "= \[\]\|= {}" --include=*.js --include=*.ts src/
python3 scripts/map_project.py --root .   # generated_files: do not edit
```

**Proof**: call the function twice and observe state that grows. A test that
passes in isolation and fails in a suite is the classic symptom.

## 4. Order and timing

**Signatures**:

- Cache/registry read before it is initialised (import order)
- Missing `await`, or an async function called synchronously
- `useEffect`/listener registered in render rather than on mount
- Singleton created lazily in two places

**Detection**: `trace_symbol` on the initialiser and on the reader; compare the
definition's file to the caller's file. Import-time side effects live in module
bodies — read the top of the file, not just the function.

**Proof**: run the failing path twice in a row. Order bugs are frequently
non-deterministic across runs.

## 5. Configuration drift

**Signature**: the code assumes a value nobody sets in this environment.

| Source | Where to look |
|--------|---------------|
| Env var | `process.env.X`, `os.environ`, `getenv` |
| Config file | default branch of a settings loader, `.env.example` |
| Feature flag | the flag store, and the code path when it is off |
| DB schema | migration history vs the columns the code selects |
| CI vs local | the CI config and the developer's shell |

**Proof**: compare the value the code expects with the value actually present in
the failing environment. Quote both.

## 6. Layer violation

**Signature**: a lower layer depends on an upper one, or domain logic reaches
into transport concerns. Usually introduced by an urgent fix.

**Detection**: the import graph from `impact.py --list`; look for edges that go
the "wrong" way (e.g. `models` importing `api`). A cycle is a strong signal.

**Proof**: the cycle in the import graph, plus the fact that the fix "works" but
breaks another consumer of the layer below.

## 7. Encoding / normalisation

**Signature**: text that compares unequal although it looks equal — Unicode
normalisation, invisible characters, trailing whitespace, CRLF vs LF,
timestamps as local time vs UTC, float vs Decimal rounding.

**Detection**: print the bytes, not the string. `repr()` and
`len(s.encode())` expose what `print` hides.

**Proof**: a failing assertion that shows both representations.

---

## Anti-patterns: what is *not* a root cause

| Claim | Why it is usually wrong |
|-------|------------------------|
| "Off-by-one in the loop" | Rarely the origin; usually downstream of a wrong index from a caller |
| "Race condition" | Only after you have excluded order and caching; races are hard to prove without instrumentation |
| "Stale cache" | Fix the invalidation once you have found which cache |
| "It's the framework/version" | Upgrade proposals need evidence that the behaviour changed in that version |
| "Just needs a null check" | A null check at the consumer hides the producer's defect; ask why the value is null |

If you cannot produce evidence, the correct output is `CAUSE NOT FOUND` with the
hypothesis table — not the most plausible guess with a confident tone.