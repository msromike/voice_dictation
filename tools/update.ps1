# Finishes an update that update.bat downloaded. Runs only from the unpacked download in
# userdata\updates, and takes the app folder from that location, never as an argument.
$ErrorActionPreference = 'Stop'
$source = Split-Path $PSScriptRoot -Parent
$extract = Split-Path $source -Parent
$updates = Split-Path $extract -Parent
$userdata = Split-Path $updates -Parent

function Stop-WithError($message) {
    Write-Host ""
    Write-Host "[ERROR] $message" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

if ($extract -notlike '*\userdata\updates\extract') {
    Stop-WithError "Run update.bat in the Voice Dictation folder, not this file."
}
$App = Split-Path $userdata -Parent
$zip = Join-Path $updates 'main.zip'
$appCode = Join-Path $App 'voice-dictation'

function Get-AppProcesses {
    # This copy's tray and engine. A command line naming no folder was started from this one.
    Get-CimInstance Win32_Process -Filter "name='pythonw.exe' or name='python.exe'" |
        Where-Object {
            $c = $_.CommandLine
            $c -and $c -match 'vdict_(tray|daemon)\.py' -and
                ($c -like "*$appCode*" -or $c -notmatch '[A-Za-z]:\\[^"]*vdict_(tray|daemon)\.py')
        }
}

Write-Host ""
Write-Host "== Checking whether Voice Dictation is running"
$running = @(Get-AppProcesses)
if ($running) {
    $answer = Read-Host "Voice Dictation is running. Close it and update? (Y/N)"
    if ($answer -notmatch '^[Yy]') { exit 0 }
    $running | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
    if (@(Get-AppProcesses)) { Stop-WithError "Voice Dictation is still running. Exit it from the tray and try again." }
    Write-Host "Closed."
} else {
    Write-Host "Not running."
}

Write-Host ""
Write-Host "== Replacing the app files. userdata and dev-flags.toml are kept."
# Files removed upstream are removed here too. robocopy: 0-7 is success, 8 and up is failure.
& robocopy $source $App /MIR /XD userdata /XF dev-flags.toml /NFL /NDL /NJH /NJS /NP
if ($LASTEXITCODE -ge 8) { Stop-WithError "Copying the new files failed (robocopy exit code $LASTEXITCODE)." }
Remove-Item $zip -Force

Write-Host ""
Write-Host "== Running the installer"
& cmd.exe /c "`"$App\vdict_install.bat`""
if ($LASTEXITCODE) { Stop-WithError "The installer stopped (exit code $LASTEXITCODE). Its window says where." }

Write-Host ""
Write-Host "== Starting Voice Dictation"
& cmd.exe /c "`"$App\vdict_run.bat`""
