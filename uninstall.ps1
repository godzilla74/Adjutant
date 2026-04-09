# Adjutant Uninstaller for Windows
$AdjutantDir  = "$env:USERPROFILE\adjutant"
$ConfigDir    = "$env:APPDATA\Adjutant"
$TaskName     = "Adjutant"
$CliDir       = "$env:USERPROFILE\.local\bin"

Write-Host ""
Write-Host "╔════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "║    Adjutant Uninstaller            ║" -ForegroundColor Yellow
Write-Host "╚════════════════════════════════════╝" -ForegroundColor Yellow
Write-Host ""

$Confirm = Read-Host "Type 'uninstall' to confirm removal"
if ($Confirm -ne "uninstall") {
    Write-Host "Uninstall cancelled."
    exit 0
}

Write-Host ""
$DelData = Read-Host "Delete your configuration and data (DB, logs, credentials)? [y/N]"

# Stop and remove scheduled task
Write-Host "Stopping Adjutant..."
Stop-ScheduledTask  -TaskName $TaskName -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "✓ Service removed" -ForegroundColor Green

# Remove config/data
if ($DelData -match '^[Yy]$') {
    Remove-Item -Recurse -Force $ConfigDir -ErrorAction SilentlyContinue
    Write-Host "✓ Configuration and data deleted" -ForegroundColor Green
} else {
    Write-Host "  Configuration kept at: $ConfigDir" -ForegroundColor Cyan
}

# Remove install directory
if (Test-Path $AdjutantDir) {
    Remove-Item -Recurse -Force $AdjutantDir -ErrorAction SilentlyContinue
    Write-Host "✓ Install directory removed" -ForegroundColor Green
}

# Remove CLI from PATH (User scope only — we never touch system PATH)
$UserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($UserPath -like "*$CliDir*") {
    $NewPath = ($UserPath -split ";" | Where-Object { $_ -ne $CliDir }) -join ";"
    [Environment]::SetEnvironmentVariable("PATH", $NewPath, "User")
    Write-Host "✓ Removed from PATH" -ForegroundColor Green
}

Write-Host ""
Write-Host "Adjutant has been uninstalled." -ForegroundColor Green
Write-Host ""
