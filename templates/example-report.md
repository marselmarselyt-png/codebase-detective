# Example report — filled in for the fixture project

A reference example of a completed investigation. It is here to show the
expected level of detail and the tone of voice. Reproduce the investigation
yourself on `tests/fixture_repo` and compare.

---

# Investigation Report: Gold customers receive a 0% discount via POST /checkout

**Case ID**: 2026-03-11-tier-discount
**Investigated by**: <agent>
**Repository state**: branch `main` @ `a1b2c3d` | uncommitted changes: no
**Verdict**: `ROOT CAUSE FOUND`
**Confidence**: `HIGH`

---

## 1. Symptom

```bash
python3 -c "
from shopcart.api import handle_checkout_request
print(handle_checkout_request({
  'customer': {'name': 'Rina', 'tier': 'gold'},
  'items': [{'sku': 'SKU-1', 'qty': 2, 'unitPrice': 25.0}]}))
"
```

**Expected**: `{'ok': True, 'total': 47.5, 'tier_used': 'GOLD', ...}`
**Actual**: `{'ok': True, 'total': 50.0, 'tier_used': 'STANDARD', ...}`

`GET /benefits?tier=gold` still returns `0.05`, so the pricing table itself is
correct — the tier never reaches it.

## 2. Scope

- Area: `shopcart/api.py`, `shopcart/models.py`, `shopcart/pricing.py`
- First bad version: unknown — the mismatch dates from the transport layer's
  first version; no commit changed the wire format.
- Reproducible: `YES` (every request, 100% of the time)

## 3. Evidence

| # | Observation | Source |
|---|-------------|--------|
| E1 | `test_pricing_unit.py` passes; `test_regression_tier.py` fails | `python3 -m unittest discover -s tests -t .` → exit 1, 3 failures |
| E2 | Pricing logic is correct for a tier string that reaches it | `shopcart/pricing.py:17` `DISCOUNTS[normalize(tier)]` |
| E3 | `Customer` silently turns a missing tier into `STANDARD` | `shopcart/models.py:26` `self.tier = tiers.normalize(tier)`, `shopcart/tiers.py:31` |
| E4 | The transport layer reads a key the API contract does not define | `shopcart/api.py:11` `TIER_FIELD = "customerTier"` |
| E5 | The documented payload field is `tier` | `docs/api.md` § POST /checkout |

```
$ python3 -m unittest discover -s tests -t .
exit code: 1   -> 3 failed, 8 passed

$ python3 scripts/trace_symbol.py --root . --symbol Customer
definition shopcart/models.py:22, call site shopcart/service.py:9
```

## 4. Root cause

**Cause**: `shopcart/api.py` reads the customer tier from `customerTier`, a
field name that exists nowhere in the wire contract; the tier therefore arrives
as `None` and is normalised to `STANDARD` before pricing.

**Location**: `shopcart/api.py:11`

**Mechanism**:

1. Client sends `customer: {name, tier: "gold"}` (`docs/api.md`).
2. `handle_checkout_request` looks up `customer["customerTier"]` → `None`
   (`api.py:11`, `api.py:20`).
3. `Customer.__init__` normalises `None` → `"STANDARD"` (`models.py:26`,
   `tiers.py:31`).
4. `apply_discount` applies the `STANDARD` rate of `0.00` (`pricing.py:17`).
5. `GET /benefits` calls `rate_for` directly, bypassing `api.py`, so it reports
   the correct 0.05 — which is what made the bug look like a pricing problem.

**Owner**: the transport layer owns the mapping from wire format to domain
values. `docs/api.md` is correct; `api.py` diverges from it.

Ruled out:

| Hypothesis | Eliminated by |
|-----------|---------------|
| Pricing table is wrong | E2, and `GET /benefits?tier=gold` returns 0.05 |
| The unit test suite is stale/misleading about the bug | E1: the suite is green *because* it never enters `api.py` |
| `normalize` rejects `gold` | `test_pricing_unit.py::test_aliases_map_to_canonical_names` passes |

## 5. Impact before change

```
risk: MEDIUM
```

- Production dependents: 0 (`shopcart/api.py` is imported by nothing in-repo)
- Tests covering this path: `tests/test_regression_tier.py` (failing)
- Public API affected: none — the change is internal; the wire contract is
  unchanged by this fix
- Not visible to static analysis: any client that has been compensating for the
  bug in its own tier logic. **If such a workaround exists, this fix could
  double-discount those customers.** Ask the payments team before deploying.

**Risky action required?** NO — one constant, no schema change.

## 6. Change made

| File | Lines | What changed | Why here |
|------|-------|--------------|----------|
| `shopcart/api.py` | 11 | `TIER_FIELD = "customerTier"` → `TIER_FIELD = "tier"` | The transport layer owns the wire-format mapping; this is where the divergence is |

**Not changed on purpose**: `shopcart/inventory.py` has an unrelated mutable
default argument bug (`ledger=[]`). It is a real defect, out of scope for this
case, and is reported in follow-up #2 rather than silently fixed here.

## 7. Verification

Before:

```
$ python3 -m unittest discover -s tests -t .
exit code: 1   -> 3 failed, 8 passed
```

After:

```
$ python3 -m unittest discover -s tests -t .
exit code: 0   -> 11 passed

$ python3 scripts/test_probe.py --root . --run --cmd "python3 -m unittest discover -s tests -t ." --compare before.json
baseline exit 1 -> now exit 0, new failures: none
```

| Check | Result | Evidence |
|-------|--------|----------|
| Reproducing test | `NOW PASSES` | `test_regression_tier.CheckoutTierTests.test_documented_payload_field_is_honoured` |
| Full suite | `PASS (exit 0)` | output above |
| Manual check | `DONE` | `curl` against a local instance returns `tier_used: "GOLD"`, `total: 47.5` |
| Other environments | `NOT RUN` | no staging access from this workspace |

Tests added by this investigation: none — `test_regression_tier.py` already
failed before the fix and passes after.

## 8. Remaining risks and follow-ups

| Risk | Likelihood | Impact | Mitigation / owner |
|------|-----------|--------|--------------------|
| Client-side workarounds compensating for the 0% discount | MEDIUM | HIGH | Payments team to confirm before rollout |
| `TIER_FIELD` is also used elsewhere | LOW | LOW | `grep -rn TIER_FIELD` returns `api.py` only |

**Not verified**: staging environment; behaviour for clients that send
`customerTier` (the old, undocumented spelling) — those requests will continue to
be treated as `STANDARD` after this fix. That is the documented behaviour for an
unknown tier, but it should be a conscious decision.

## 9. Next steps

1. Confirm with payments whether any client compensates for the missing discount — payments team
2. Fix the mutable default argument in `shopcart/inventory.py` — separate case
3. Add a contract test that validates every documented field name in `docs/api.md` — backend

---

### Confidence justification

**HIGH**: the defect was reproduced before the change (exit code 1), the cause is
cited to a single line that provably contradicts the documented contract, and
the same command returns exit code 0 afterwards with no new failures. The one
open question — whether any client compensates for the bug in its own code —
concerns deployment risk, not the correctness of the diagnosis. It would drop
this to MEDIUM if the fix were applied to a fleet where clients are known to
apply their own discount logic.