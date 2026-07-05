# Install voice dictation tray to Windows startup
# Creates shortcut in user's Startup folder

$startupFolder = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$vdictTrayPath = Join-Path $scriptPath "vdict_tray.py"
$pythonwPath = (Get-Command pythonw.exe).Source
$shortcutPath = Join-Path $startupFolder "VoiceDictation.lnk"

# Create shortcut
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = $pythonwPath
$Shortcut.Arguments = "`"$vdictTrayPath`""
$Shortcut.WorkingDirectory = $scriptPath
$Shortcut.Description = "Voice Dictation Tray"
$Shortcut.Save()

Write-Host "Installed to startup: $shortcutPath"
Write-Host "Voice dictation will launch automatically on next login"
