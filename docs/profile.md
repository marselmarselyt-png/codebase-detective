# Codebase Detective

> **Investigate First. Modify Later.**

An AI agent skill that makes a coding agent behave like a software detective
instead of a guess-driven editor.

It **maps an unfamiliar repository**, **traces root causes across files**,
**analyses the blast radius before editing**, **runs the tests that actually
exist**, and **reports what it knows — and what it does not**, with a confidence
level and real exit codes.

Python 3 standard library only. No `pip install`. Nothing added to your repo.

---

## Install

**opencode, all projects**

```bash
git clone https://github.com/marselmarselyt-png/codebase-detective.git \
  ~/.config/opencode/skills/codebase-detective
```

**opencode, one project**

```bash
cd /path/to/your/project
git clone https://github.com/marselmarselyt-png/codebase-detective.git \
  .opencode/skills/codebase-detective
```

**Claude Code**

```bash
git clone https://github.com/marselmarselyt-png/codebase-detective.git \
  ~/.claude/skills/codebase-detective
```

No git? Download the zip, extract it, rename the folder to
`codebase-detective`. Any other agent: point it at `SKILL.md`.

**Requirements:** Python 3.9+. Nothing else.

## Try it

```bash
cd ~/.config/opencode/skills/codebase-detective
python3 scripts/map_project.py --root tests/fixture_repo
```

Restart opencode, open your project, and ask:

> Checkout throws a 500 since Tuesday. `POST /api/orders` fails only for orders
> with more than three line items. Find out why and fix it.

Full walkthrough with real terminal output:
**[docs/getting-started.md](https://github.com/marselmarselyt-png/codebase-detective/blob/main/docs/getting-started.md)**

---

**MIT licensed.** Contributions and bug reports welcome — see
[Contributing](https://github.com/marselmarselyt-png/codebase-detective#contributing).

[The longer essay →](docs/extension.md) on why agents get investigations wrong
and what this skill does differently.
