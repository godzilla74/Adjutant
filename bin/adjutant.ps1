# bin/adjutant.ps1 — Adjutant CLI for Windows
param([string]$Command)

$AdjutantDir = Split-Path -Parent $PSScriptRoot
$LogFile = "$env:APPDATA\Adjutant\adjutant.log"
$TaskName = "Adjutant"

function Start-Adjutant  { Start-ScheduledTask -TaskName $TaskName }
function Stop-Adjutant   { Stop-ScheduledTask  -TaskName $TaskName }
function Restart-Adjutant {
    Stop-ScheduledTask  -TaskName $TaskName -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Start-ScheduledTask -TaskName $TaskName
}

switch ($Command) {
    "start" {
        Start-Adjutant
        Write-Host "Adjutant started."
    }
    "stop" {
        Stop-Adjutant
        Write-Host "Adjutant stopped."
    }
    "restart" {
        Restart-Adjutant
        Write-Host "Adjutant restarted."
    }
    "logs" {
        Get-Content -Path $LogFile -Wait -Tail 50
    }
    "update" {
        Write-Host "Updating Adjutant..."
        Set-Location $AdjutantDir
        git pull
        & ".venv\Scripts\pip" install --quiet -r requirements.txt
        Set-Location ui
        npm install --silent
        npm run build --silent
        Set-Location $AdjutantDir
        Restart-Adjutant
        Write-Host "Adjutant updated and restarted."
    }
    "uninstall" {
        Write-Host ""
        Write-Host "This will permanently remove Adjutant and all your data."
        $Confirm = Read-Host "Type 'uninstall' to confirm"
        if ($Confirm -eq "uninstall") {
            Stop-Adjutant -ErrorAction SilentlyContinue
            Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
            Remove-Item -Recurse -Force "$env:APPDATA\Adjutant" -ErrorAction SilentlyContinue
            Remove-Item -Recurse -Force $AdjutantDir -ErrorAction SilentlyContinue
            Write-Host "Adjutant has been uninstalled."
        } else {
            Write-Host "Uninstall cancelled."
        }
    }
    default {
        Write-Host "Usage: adjutant {start|stop|restart|update|logs|uninstall}"
        exit 1
    }
}
