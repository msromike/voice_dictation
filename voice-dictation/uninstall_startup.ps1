# Remove voice dictation tray from Windows startup

$startupFolder = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
$shortcutPath = Join-Path $startupFolder "VoiceDictation.lnk"

if (Test-Path $shortcutPath) {
    Remove-Item $shortcutPath -Force
    Write-Host "Removed from startup: $shortcutPath"
} else {
    Write-Host "Shortcut not found in startup folder"
}
