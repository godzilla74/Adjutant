# install.ps1 — Adjutant installer for Windows
# Usage: irm https://adjutantapp.com/install.ps1 | iex

$ErrorActionPreference = "Stop"
$AdjutantDir = "$env:USERPROFILE\adjutant"
$RepoUrl = "https://github.com/godzilla74/Adjutant.git"
$ConfigDir = "$env:APPDATA\Adjutant"
$ConfigFile = "$ConfigDir\config.env"
$DbFile = "$ConfigDir\adjutant.db"
$LogFile = "$ConfigDir\adjutant.log"
$TaskName = "Adjutant"

Write-Host ""
Write-Host "╔════════════════════════════════════╗" -ForegroundColor Blue
Write-Host "║    Welcome to Adjutant Installer   ║" -ForegroundColor Blue
Write-Host "╚════════════════════════════════════╝" -ForegroundColor Blue
Write-Host ""

# Check/install Python 3.12+
$PythonExe = $null
try {
    $ver = (python --version 2>&1).ToString()
    if ($ver -match "Python (\d+)\.(\d+)") {
        if ([int]$Matches[1] -ge 3 -and [int]$Matches[2] -ge 12) {
            $PythonExe = "python"
            Write-Host "✓ $ver" -ForegroundColor Green
        }
    }
} catch {}

if (-not $PythonExe) {
    Write-Host "Installing Python 3.12..."
    winget install -e --id Python.Python.3.12 --silent
    $PythonExe = "python"
}

# Check/install Node 18+
$NodeOk = $false
try {
    $nodeVer = (node --version 2>&1).ToString().TrimStart("v").Split(".")[0]
    if ([int]$nodeVer -ge 18) { $NodeOk = $true; Write-Host "✓ Node.js $(node --version)" -ForegroundColor Green }
} catch {}
if (-not $NodeOk) {
    Write-Host "Installing Node.js..."
    winget install -e --id OpenJS.NodeJS.LTS --silent
}

# Check/install git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Installing git..."
    winget install -e --id Git.Git --silent
}
Write-Host "✓ git" -ForegroundColor Green

# Check if already installed
if (Test-Path $AdjutantDir) {
    Write-Host "Adjutant is already installed at $AdjutantDir" -ForegroundColor Yellow
    Write-Host "Run 'adjutant update' to update to the latest version."
    exit 0
}

# Clone repo
Write-Host "Downloading Adjutant..."
git clone --quiet $RepoUrl $AdjutantDir

# Python venv + deps
Write-Host "Installing Python dependencies..."
& $PythonExe -m venv "$AdjutantDir\.venv"
& "$AdjutantDir\.venv\Scripts\pip" install --quiet --upgrade pip
& "$AdjutantDir\.venv\Scripts\pip" install --quiet -r "$AdjutantDir\requirements.txt"

# Node deps
Write-Host "Installing UI dependencies..."
Push-Location "$AdjutantDir\ui"
npm install --silent
Pop-Location

# Config directory
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null

# Setup prompts
Write-Host ""
Write-Host "Let's set up your Adjutant." -ForegroundColor Yellow
Write-Host ""

$AgentName = Read-Host "What would you like to name your AI assistant? [Hannah]"
if (-not $AgentName) { $AgentName = "Hannah" }

do {
    $AgentPassword  = Read-Host "Choose a password to protect your Adjutant" -AsSecureString
    $AgentPassword2 = Read-Host "Confirm password" -AsSecureString
    $p1 = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($AgentPassword))
    $p2 = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($AgentPassword2))
    if ($p1 -ne $p2) { Write-Host "Passwords don't match. Try again." -ForegroundColor Red }
} while ($p1 -ne $p2)
$AgentPasswordPlain = $p1

do {
    $ApiKey = Read-Host "Your Anthropic API key (from console.anthropic.com)"
    Write-Host -NoNewline "Testing your API key..."
    try {
        $resp = Invoke-WebRequest -Uri "https://api.anthropic.com/v1/models" `
            -Headers @{"x-api-key"=$ApiKey; "anthropic-version"="2023-06-01"} `
            -UseBasicParsing -ErrorAction SilentlyContinue
        if ($resp.StatusCode -eq 200) { Write-Host " ✓" -ForegroundColor Green; break }
    } catch {}
    Write-Host " That key doesn't seem to work — double-check and try again." -ForegroundColor Red
} while ($true)

Write-Host ""
Write-Host "Now let's help $AgentName get to know you."
$OwnerName = Read-Host "  Your name"
Write-Host "  Tell $AgentName about yourself and your business"
Write-Host "  (role, industry, goals — the more they know, the more useful they'll be):"
$OwnerBio = Read-Host "  >"

Write-Host ""
Write-Host "Let's add your first product."
$ProductName = Read-Host "  Business name"
$ProductDesc = Read-Host "  What does it do? (one sentence)"
$ProductId = $ProductName.ToLower() -replace ' ', '-' -replace '[^a-z0-9-]', ''

# Write config
$ConfigContent = @"
ANTHROPIC_API_KEY=$ApiKey
AGENT_PASSWORD=$AgentPasswordPlain
AGENT_NAME=$AgentName
AGENT_OWNER_NAME=$OwnerName
AGENT_OWNER_BIO=$OwnerBio
ADJUTANT_SEED_PRODUCT_ID=$ProductId
ADJUTANT_SEED_PRODUCT_NAME=$ProductName
ADJUTANT_SEED_PRODUCT_DESC=$ProductDesc
AGENT_DB=$DbFile
"@
$ConfigContent | Out-File -FilePath $ConfigFile -Encoding UTF8
(Get-Item $ConfigFile).Attributes = "Hidden"

# Build UI
Write-Host "Building the interface..."
Push-Location "$AdjutantDir\ui"
npm run build --silent
Pop-Location

# Register Task Scheduler task
$UvicornPath = "$AdjutantDir\.venv\Scripts\uvicorn.exe"
$Action = New-ScheduledTaskAction -Execute $UvicornPath `
    -Argument "backend.main:app --host 0.0.0.0 --port 8001" `
    -WorkingDirectory $AdjutantDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 0) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$Env = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
    -Settings $Settings -Principal $Env -Force | Out-Null
# Set ADJUTANT_CONFIG environment variable for the task
$task = Get-ScheduledTask -TaskName $TaskName
$task.Definition.Actions[0].EnvironmentVariables = @{"ADJUTANT_CONFIG"=$ConfigFile}
Set-ScheduledTask -TaskName $TaskName -InputObject $task.Definition | Out-Null
Start-ScheduledTask -TaskName $TaskName

# Install CLI
$BinDir = "$env:USERPROFILE\.local\bin"
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
Copy-Item "$AdjutantDir\bin\adjutant.ps1" "$BinDir\adjutant.ps1" -Force
$WrapperContent = "@echo off`npowershell -ExecutionPolicy Bypass -File `"%~dp0adjutant.ps1`" %*"
$WrapperContent | Out-File -FilePath "$BinDir\adjutant.cmd" -Encoding ASCII

# Add to PATH if needed
$CurrentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($CurrentPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable("PATH", "$CurrentPath;$BinDir", "User")
    $env:PATH = "$env:PATH;$BinDir"
}

# Done
Write-Host ""
Write-Host "╔════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║    Adjutant is running! 🎉         ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  Open: http://localhost:8001" -ForegroundColor Cyan
Write-Host "  Manage: adjutant {start|stop|restart|update|logs|uninstall}" -ForegroundColor Yellow
Write-Host ""

Start-Sleep -Seconds 2
Start-Process "http://localhost:8001"
