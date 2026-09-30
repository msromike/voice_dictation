---
name: commit-per-protocol
description: Run this project's commit protocol -- QA gates and a structured commit message. Invoke when the user says "commit per protocol", or asks to commit/stage work in this repo. Never pushes.
---

# Commit Per Protocol

ON COMMAND only. Never invoke autonomously. Never `git push`.

One working tree, one branch, whatever's currently checked out. Docs and
code live together -- no separate tree, no separate commit for either.

EVERY STEP EMITS OUTPUT, including "nothing found". A step with no visible
result cannot be audited and will be assumed skipped.

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

    ./venv/Scripts/ruff.exe check .
    ./venv/Scripts/pyright.exe
    ./venv/Scripts/vulture.exe voice-dictation tools/vulture_whitelist.py --min-confidence 60
    ./venv/Scripts/python.exe tools/check_docstrings.py

- ruff, pyright and vulture must be CLEAN. All three have been at zero; a
  finding here is new unless the owning plan records it.
- vulture needs --min-confidence 60; above that it stops reporting unused
  METHODS, which is the whole reason it is here. Its false positives live in
  tools/vulture_whitelist.py -- read that file before "fixing" anything it
  lists.
- check_docstrings must be 0. Any count above zero is a regression. Treat
  it as a FAIL.
- If a tool is missing: EMIT "step 2 skipped -- <tool> not installed". Never
  pass silently.
- RUF100 (stale noqa) is the one exception: never a judgment call, ruff has
  already proven the suppression is dead. Fix it inline -- drop the unused
  code from the noqa comment -- re-run step 2, and EMIT what was removed. Do
  not stop to ask. Every other failure (ruff non-RUF100, pyright, vulture,
  check_docstrings) still stops.
- Before reporting a finding as undecided, run the same tool on HEAD
  (git stash, run, git stash pop) and diff. A finding present on HEAD is
  expected and needs no escalation; the check at commit time is that
  nothing NEW appeared, not that the count is zero.
- FAIL -> stop. Name the violation and the fix. Wait.
  - Not a binary. Three resume paths: fix it now; defer the whole commit; or
    get explicit authorization to proceed with it unresolved. On
    authorization, record it in the owning plan if nothing already does, then
    proceed. The gate stays live for the next commit either way --
    authorization is not suppression.
  - On resume: re-run step 2 ONLY. Never restart from step 1.
- PASS -> continue.

Then the complexity REPORT. Skip when no .py is staged.

    ./venv/Scripts/ruff.exe check $(git diff --staged --name-only -- '*.py') \
        --select C901 --ignore-noqa --config "lint.mccabe.max-complexity=1"

- Prints every touched function with its real score, suppressions included.
  EMIT the list.
- NOT a gate. Non-zero exit is expected. Do not restructure anything in
  response and do not add noqa. Hand the numbers over.
- Unconditional on purpose: a score is printed whether it passes or not, so
  lowering one buys nothing.

Then the imperative-comment REPORT. No .py staged -> skip.

    git diff --staged -U0 -- '*.py' | grep -niE \
        "^\+.*(keep it that way|do not |never |always|locked|decided|no need to)"

- Hit -> EMIT it. Cites an external fact -> legit, skim and move on. Backed
  only by preference -> say so in the commit body. No hits -> EMIT "none
  found".
- Never reword a comment to dodge this report -- same disease as a gate.

Nothing runs per edit. This step is the first and only check, not a
formality.

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
                             and why. MANDATORY whenever non-empty, against
                             the rule above -- an extraction done to move a
                             lint score reads exactly like tidying.
    [LOGIC & PATTERN SHIFTS] non-obvious decisions, architecture, gotchas

No session process: no gate outcomes, no overrides, no "kept separate on
purpose", no "X is next". Deferred work lives in new_next.md.

Capture the SHA.

## 5. Terminator

- "I committed this to [branch] with the commit message [message]"
- Then a phase report: which of steps 2 and 3 ran, and which were skipped
  and why.
- Hard stop. Do not push. No further commands.
