---
name: commit-per-protocol
description: Run this project's commit protocol -- QA gates and a structured commit message. Invoke when the user says "commit per protocol", or asks to commit/stage work in this repo. Pushes the current branch after committing.
---

# Commit Per Protocol

Push after every commit. aorus and the laptop share one private GitHub repo,
and an unpushed commit never reaches the other machine.

One working tree, one branch, whatever's currently checked out. Docs and
code live together -- no separate tree, no separate commit for either.

## 1. Read

- `git status`
- `git add -A`
- `git diff --staged --stat`
- `git diff --staged --diff-filter=M -- . ':(exclude)*lock*'`
- Deleted/added/renamed files are self-documenting from status and stat.
  Document them by filename. Only modified files need diff review.
- Deleted or modified files in `git status` are intentional. Do not pause.
- EMIT: code changed? docs changed? which subsystems?

## 2. Checks

No `.py` files staged -> skip this entire step, EMIT "step 2 skipped -- no
Python files staged." These tools check the code tree; nothing being
committed touches it.

Cheap first. Stop on the first failure.

    python -m ruff check .
    python -m pyright
    python -m vulture voice-dictation tools/vulture_whitelist.py --min-confidence 60
    python tools/check_docstrings.py

- ruff and pyright must be CLEAN.
- vulture is a REPORT, never a stop: EMIT every finding, then continue.
  Unreferenced code is the normal state mid-refactor. It needs
  --min-confidence 60; above that it stops reporting unused METHODS, which
  is the whole reason it is here. Its false positives live in
  tools/vulture_whitelist.py -- read that file before "fixing" anything it
  lists.
- check_docstrings must be 0. Any count above zero is a regression. Treat
  it as a FAIL.
- If a tool is missing: EMIT "step 2 skipped -- <tool> not installed". Never
  pass silently.
- RUF100 (stale noqa) is the one exception: never a judgment call, ruff has
  already proven the suppression is dead. Fix it inline -- drop the unused
  code from the noqa comment -- re-run step 2, and EMIT what was removed. Do
  not stop to ask. Every other failure (ruff non-RUF100, pyright,
  check_docstrings) still stops.
- FAIL -> fix it, re-run step 2, EMIT what changed. Stop only when the fix
  would change behavior.
- PASS -> continue.

Then the complexity REPORT. Skip when no .py is staged.

    python -m ruff check $(git diff --staged --name-only -- '*.py') \
        --select C901 --ignore-noqa --config "lint.mccabe.max-complexity=1"

- Prints every touched function with its real score, suppressions included.
  EMIT the list.
- NOT a gate. Non-zero exit is expected. Do not restructure anything in
  response and do not add noqa. Hand the numbers over.
- Unconditional on purpose: a score is printed whether it passes or not, so
  lowering one buys nothing.

## 3. Derive and write

Invoking this protocol AUTHORIZES the writes below. Do not stall for approval.

Derive from the diff. Do not ask questions the diff answers. Do not prompt for
things that are usually absent.

WRITE DIRECTLY, no approval round:

- The commit message. It is read by grep, not by the user, and is amendable.
- User-visible behavior changed -> write the CHANGELOG.md entry.
- Menu labels or UI strings changed -> fix the README sections referencing them.

EMIT what was written. If nothing was derived, say so.

## 4. Commit

One commit, on the current branch. Semantic header (`feat:`, `fix:`, `chore:`,
`docs:`). Body = the difference, minus what the diff already shows:

    [ARCHIVED FILES]         path -- destination and reason
    [DELETED FILES]          path -- reason
    [SCHEMA SHIFTS]          tables, columns, migrations, indexes
    [STRUCTURE]              functions added, split, extracted or renamed,
                             and why
    [LOGIC & PATTERN SHIFTS] non-obvious decisions, architecture, gotchas

No session process: no gate outcomes, no overrides, no "kept separate on
purpose", no "X is next". Deferred work lives in new_next.md.

Capture the SHA. Then push:

    git push -u origin HEAD

## 5. Terminator

- "I committed and pushed this to [branch] with the commit message [message]"
- Then a phase report: which of steps 2 and 3 ran, and which were skipped
  and why.
- A failed push is reported with git's exact output, never retried silently.
