---
name: sync
description: Sync this repo with its private GitHub copy so aorus and the laptop stay identical. Invoke when Mike says "sync", or says he is sitting down at or leaving a machine.
---

# Sync

GitHub is robocopy in the cloud with versioning. Mike runs this when he sits
down at a machine and when he leaves it. Everything is tracked except userdata/,
which is per machine (.gitignore). He never uses the app on both machines at once.

No QA gates: a sync commit is a snapshot, not a code commit. Code commits still
go through commit-per-protocol.

## 1. Upload

    git add -A
    git commit -m "sync: <COMPUTERNAME> <yyyy-MM-dd HH:mm>"

Nothing to commit -> continue. The app may stay running.

## 2. Anything to download?

    git fetch origin
    git rev-list --count HEAD..origin/<current branch>

0 -> skip to step 4.

## 3. Download

A commit that untracks a file reaches this machine as a delete, and the pull
removes it from disk. List incoming deletes:

    git diff --name-only --diff-filter=D HEAD...origin/<current branch>

Each one that exists here and the incoming .gitignore now ignores
(`git show origin/<branch>:.gitignore`) is an untrack, not a delete: run
`git rm --cached <path>` and commit "sync: <COMPUTERNAME> untracks <what>"
before pulling. Any other delete of a file that differs from HEAD -> show it
to Mike and ask.

Find this checkout's app. voice_dictation-stable also matches "vdict" and is
not this app; the path match below excludes it.

    Get-CimInstance Win32_Process -Filter "name='pythonw.exe' or name='python.exe'" |
        Where-Object CommandLine -match 'voice_dictation\\voice-dictation\\vdict'

Running -> tell Mike the pull would replace files it holds open, and ask him to
exit it from the tray or to let you kill it (Stop-Process on those PIDs).
Wait for his answer. Never kill without it.

    git pull --no-rebase origin <current branch>

Any conflict -> stop, show `git status`, ask.

## 4. Push

    git push -u origin HEAD

## 5. Report

One line each: uploaded (N files, or nothing), downloaded (N commits, or
nothing), pushed. If the app was stopped, say it is safe to relaunch. Never
start it.

## New machine

    git clone -b dev https://github.com/msromike/voice_dictation.git C:\bin\repos\voice_dictation

The clone carries no Python and no Whisper models. Dictating on a new machine
needs global Python 3.12, its packages and a first model download.
