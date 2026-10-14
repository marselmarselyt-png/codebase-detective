# Testing and verification

The rule this file exists to enforce:

> **A test result you did not run is not a test result.**

---

## Discovery

```bash
python3 scripts/test_probe.py --root . --list
```

Detection is based on manifests, not guesses:

| Stack | Signal | Command | Exit 0 means |
|-------|--------|---------|-------------|
| Node | `vitest`/`jest`/`mocha` in `package.json` | `npx vitest run` | suite passed |
| Node | `test` script | `npm test` | script's own command passed — check what it does |
| Python | `pytest.ini`/`pyproject.toml`/test files | `python3 -m pytest -q` | suite passed |
| Python | `unittest`-style tests, no pytest config | `python3 -m unittest discover` | suite passed |
| Rust | `Cargo.toml` | `cargo test` | suite passed |
| Go | `go.mod` | `go test ./...` | all packages passed |
| JVM | `pom.xml` / `gradlew` | `mvn test` / `./gradlew test` | build+tests passed |

If detection returns nothing, the honest status is `NOT RUN` and the report
must say so.

## Baseline first

When the suite might already be red:

```bash
# BEFORE any edit
python3 scripts/test_probe.py --root . --run --baseline /tmp/before.json

# AFTER the edit
python3 scripts/test_probe.py --root . --run --compare /tmp/before.json
```

The comparison reports baseline exit code, current exit code, new failures,
fixed failures, and a verdict. This is the only defensible way to say "my change
introduced nothing".

## Interpreting exit codes

| Exit | Meaning | May you claim |
|------|---------|---------------|
| `0` | Command completed successfully | "`<command>` exited 0" — quote it verbatim |
| `1` (tests) | Assertion/test failure | "the suite is red" — quote the failing test names |
| `2` | Usage or configuration error | Nothing about test correctness; fix the invocation first |
| `124`/timeout | Suite did not finish | "TIMEOUT — no result"; never infer pass/fail |
| missing binary | Toolchain absent | "NOT RUN - `<tool>` not installed" |

A command that prints "0 failed" and then exits 127 has still not run. Trust
the exit code over the prose in the output.

## Writing a reproducing test

A bug fix without a reproducing test is unverified work.

```python
def test_documented_payload_field_is_honoured(self):
    result = handle_checkout_request(checkout_body("gold"))
    self.assertEqual(result["tier_used"], "GOLD")
```

Requirements:

1. **Fails on the unfixed tree.** Verify this — run it before the fix and keep
   the output.
2. **Passes after the fix.**
3. **Tests behaviour, not implementation.** Assert on the observable result; a
   test that asserts on internal call order breaks on every refactor.
4. **Lives at the boundary where the bug appeared.** If the bug only appears
   through the HTTP layer, a unit test three layers down will pass forever.
5. **Has a name that describes the contract**, not the implementation:
   `test_documented_payload_field_is_honoured` beats `test_api_2`.

## Anti-patterns that turn tests green without fixing anything

- Adding a `None` check in the consumer and leaving the producer broken.
- Changing the assertion to match the buggy output.
- Marking the failing test `@unittest.skip` "until the refactor lands".
- Loosening a tolerance to make a value comparison pass.
- Fixing the code so the test no longer exercises the broken path.
- Deleting a test that is inconvenient.

All of these make the suite green and the bug alive. The regression test in
`tests/fixture_repo/tests/test_regression_tier.py` is designed to reject the
most plausible wrong fix: it fails even if someone "fixes" `tiers.normalize` to
return a non-default value, because that breaks the documented fallback for
unknown tiers.

## The honest-report checklist

Before writing "tests pass" into a report, confirm all five:

- [ ] The command is quoted exactly as run, including flags and cwd.
- [ ] The exit code is quoted.
- [ ] The comparison against a baseline (if the suite was already red) is shown.
- [ ] The specific tests covering the changed path are named, not just "the suite".
- [ ] Anything not run is stated as `NOT RUN`, with the reason.

## Reporting template

```
$ cd <root> && <command>
exit code: <n>
<one line: what passed / what failed>

baseline (before change): exit <n>
current  (after change) : exit <n>
new failures: <list or none>
```

That block, pasted verbatim into the report, is the whole verification section.