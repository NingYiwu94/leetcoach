$ShortcutPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "LeetCoach.lnk"

if (Test-Path $ShortcutPath) {
    Remove-Item -LiteralPath $ShortcutPath -Force
    Write-Host "Removed Desktop shortcut: $ShortcutPath"
} else {
    Write-Host "Desktop shortcut was not found."
}
