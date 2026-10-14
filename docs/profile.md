# Codebase Detective

> **Investigate First. Modify Later.**

An AI agent skill that makes a coding agent behave like a software detective
instead of a guess-driven editor.

It **maps an unfamiliar repository**, **traces root causes across files**,
**analyses the blast radius before editing**, **runs the tests that actually
exist**, and **reports what it knows — and what it does not**, with a confidence
level and real exit codes.

- Python 3 standard library only. No `pip install`. Nothing added to your repo.
- Works with opencode, Claude Code, and any agent that loads a `SKILL.md`.
- 31 automated tests over every script, plus a deliberately broken fixture
  project with three planted cross-file bugs.

**MIT licensed.** Contributions and bug reports welcome — see
[Contributing](#contributing).

[Read the longer essay →](docs/extension.md) on why agents get investigations
wrong and what this skill does differently.
