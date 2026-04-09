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
        Write-Host "This will permanently remove Adjutant."
        $Confirm = Read-Host "Type 'uninstall' to confirm"
        if ($Confirm -eq "uninstall") {
            $DelData = Read-Host "Delete your configuration and data (DB, logs, credentials)? [y/N]"
            Stop-Adjutant -ErrorAction SilentlyContinue
            Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
            if ($DelData -match '^[Yy]$') {
                Remove-Item -Recurse -Force "$env:APPDATA\Adjutant" -ErrorAction SilentlyContinue
            }
            Remove-Item -Recurse -Force $AdjutantDir -ErrorAction SilentlyContinue
            $CliDir = "$env:USERPROFILE\.local\bin"
            $UserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
            if ($UserPath -like "*$CliDir*") {
                $NewPath = ($UserPath -split ";" | Where-Object { $_ -ne $CliDir }) -join ";"
                [Environment]::SetEnvironmentVariable("PATH", $NewPath, "User")
            }
            Write-Host "Adjutant has been uninstalled."
        } else {
            Write-Host "Uninstall cancelled."
        }
    }
    "telegram" {
        if ($args[0] -ne "setup") {
            Write-Host "Usage: adjutant telegram setup"
            exit 1
        }
        Write-Host ""
        Write-Host "Setting up Telegram remote access..."

        $ConfigFile = "$env:APPDATA\Adjutant\config.env"

        if (-not (Test-Path $ConfigFile)) {
            Write-Host "Config file not found at: $ConfigFile" -ForegroundColor Red
            Write-Host "Run the installer first."
            exit 1
        }

        $Token = (Get-Content $ConfigFile | Where-Object { $_ -match "^TELEGRAM_BOT_TOKEN=" }) -replace "^TELEGRAM_BOT_TOKEN=", ""

        if (-not $Token) {
            Write-Host "TELEGRAM_BOT_TOKEN not set in config." -ForegroundColor Red
            Write-Host ""
            Write-Host "Steps:"
            Write-Host "  1. Message @BotFather on Telegram -> /newbot -> copy the token"
            Write-Host "  2. Add to $ConfigFile`:"
            Write-Host "       TELEGRAM_BOT_TOKEN=your_token_here"
            Write-Host "  3. Run 'adjutant telegram setup' again"
            exit 1
        }

        Write-Host "Token found. Checking for recent messages..."
        try {
            $resp = Invoke-WebRequest -Uri "https://api.telegram.org/bot$Token/getUpdates?limit=10" -UseBasicParsing
            $data = ($resp.Content | ConvertFrom-Json)
            $msgs = $data.result | Where-Object { $_.message -and $_.message.from } | ForEach-Object { $_.message }
            $ChatId = ($msgs | Select-Object -Last 1).from.id
        } catch {
            $ChatId = $null
        }

        if (-not $ChatId) {
            Write-Host ""
            Write-Host "No recent messages found." -ForegroundColor Yellow
            Write-Host "  1. Open Telegram and find your bot"
            Write-Host "  2. Send any message to it"
            Write-Host "  3. Run 'adjutant telegram setup' again"
            exit 1
        }

        $content = Get-Content $ConfigFile
        if ($content -match "^TELEGRAM_CHAT_ID=") {
            $content = $content -replace "^TELEGRAM_CHAT_ID=.*", "TELEGRAM_CHAT_ID=$ChatId"
        } else {
            $content += "TELEGRAM_CHAT_ID=$ChatId"
        }
        $content | Out-File -FilePath $ConfigFile -Encoding UTF8

        Write-Host ""
        Write-Host "✓ Telegram configured! Chat ID: $ChatId" -ForegroundColor Green
        Write-Host "Run 'adjutant restart' to activate."
    }
    default {
        Write-Host "Usage: adjutant {start|stop|restart|update|logs|uninstall|telegram}"
        exit 1
    }
}
