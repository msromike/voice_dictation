---
name: sync
description: Commit all changes, pull origin, push. Invoke when Mike says "sync" or says he is starting or leaving a session on a machine.
---

# Sync

Tracked: everything except userdata/ and *.flac (.gitignore).
Sync commits skip commit-per-protocol's QA gates. Code commits do not.

## 1. Upload

    git add -A
    git commit -m "sync: <COMPUTERNAME> <yyyy-MM-dd HH:mm>"

Nothing to commit -> continue. The app may stay running.

## 2. Anything to download?

    git fetch origin
    git rev-list --count HEAD..origin/<current branch>

0 -> skip to step 4.

## 3. Download

List incoming deletes:

    git diff --name-only --diff-filter=D HEAD...origin/<current branch>

Each that exists here and is ignored by the incoming .gitignore
(`git show origin/<current branch>:.gitignore`): `git rm --cached <path>`,
commit "sync: <COMPUTERNAME> untracks <what>", then pull. Any other delete of a
file that differs from HEAD -> show it to Mike and ask.

Find this checkout's app:

    Get-CimInstance Win32_Process -Filter "name='pythonw.exe' or name='python.exe'" |
        Where-Object CommandLine -match 'voice_dictation\\voice-dictation\\vdict'

Running -> ask Mike to exit it from the tray. Wait until he says it is down.

    git pull --no-rebase origin <current branch>

Any conflict -> stop, show `git status`, ask.

## 4. Push

    git push -u origin HEAD

## 5. Report

One line each: uploaded (N files, or nothing), downloaded (N commits, or
nothing), pushed. App stopped -> say it is safe to relaunch. Never start it.

## New machine

    git clone -b dev https://github.com/msromike/voice_dictation.git C:\bin\repos\voice_dictation
    New-Item -ItemType Junction -Path .claude\skills -Target (Resolve-Path .agents\skills).Path

The junction is how Claude finds the skills; git does not store it. The clone
has no Python and no Whisper models. Dictating needs global Python 3.12,
`python -m pip install -r requirements.txt`, and a first model download.
