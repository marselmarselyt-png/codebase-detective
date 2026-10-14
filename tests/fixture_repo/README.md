# fixture_repo

A deliberately broken mini-project used to exercise the Codebase Detective skill
and its scripts. It is a test fixture, not real software.

## The project

`shopcart/` is a four-layer order pipeline:

```
api.py  (transport)  ->  service.py  (application)  ->  models.py / pricing.py  (domain)
                                                      \-> tiers.py
                                                      \-> inventory.py
```

Standard library only, so it runs anywhere:

```bash
cd tests/fixture_repo
python3 -m unittest discover -s tests -t . -v
```

## What it is for

| Test file                                        | Before the fix | Purpose |
|--------------------------------------------------|----------------|---------|
| `tests/test_pricing_unit.py`                      | PASSES         | Shows a green unit suite can still miss a cross-file bug |
| `tests/test_regression_tier.py`                   | FAILS          | The cross-file tier bug, seen from the HTTP boundary |
| `tests/test_regression_inventory.py`              | FAILS          | A shared-state regression that only shows between calls |

The agent under test is given `shopcart/`, the symptom, and nothing else. It is
**not** given `BUGS.md` - that file is the grader's ground truth.

## web/ - a JavaScript twin

`web/` reproduces the same class of bug in JavaScript (`auth.verify` returns a
boolean, `api.js` reads `.valid` off it) so multi-language tracing can be
tested with `node web/src/api.js`.

See `../BUGS.md` for the ground truth and the expected evidence trail.