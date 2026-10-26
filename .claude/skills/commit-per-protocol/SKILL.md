---
name: commit-per-protocol
description: Run this project's commit protocol -- checks, docs, a structured commit message, push. Invoke when the user says "commit per protocol", or asks to commit/stage work in this repo.
---

# Commit Per Protocol

One commit on the current branch, docs and code together, then push.

## 1. Stage

    git add -A
    git diff --staged --stat
    git diff --staged --diff-filter=M -- . ':(exclude)*lock*'

Everything in `git status` is intentional. Do not pause over it.

## 2. Checks

Skip when no `.py` is staged.

    python -m ruff check .
    python -m pyright
    python tools/check_docstrings.py

All three must be clean. RUF100 (stale noqa): drop the dead code from the
comment and re-run. Any other failure: fix and re-run; stop and ask only if the
fix changes behavior. A tool missing: say so, never pass silently.

## 3. Docs

Authorized, no approval round:

- User-visible behavior changed -> one plain line in CHANGELOG.md under the
  next version's heading (add the heading if there isn't one). What changed,
  not why.
- UI text changed -> fix the README sections that quote it.
- A doc now states something false -> correct it.

## 4. Commit and push

Semantic header (`feat:`, `fix:`, `chore:`, `docs:`). Body: what the diff does
not show, under whichever apply:

    [DELETED FILES]          path -- reason
    [SCHEMA SHIFTS]          config fields, tables, defaults
    [STRUCTURE]              functions added, split or renamed, and why
    [LOGIC & PATTERN SHIFTS] non-obvious decisions and gotchas

No session process: no gate outcomes, no overrides, no "X is next".

Write the message to a file and `git commit -F <file>`; PowerShell does not
pipe a here-string to `-F -`. Then:

    git push -u origin HEAD

## 5. Report

One line: branch, short SHA, subject, pushed. Then what step 3 changed. A failed push: git's exact output, no silent retry.
