# Check MT5 EA Integration Status
# Run this from PowerShell to verify everything is connected

Write-Host "`n===============================================================" -ForegroundColor Cyan
Write-Host "   BLACK KNIGHT - SYSTEM INTEGRATION CHECK" -ForegroundColor Cyan
Write-Host "===============================================================`n" -ForegroundColor Cyan

$projectPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$localCredentialsPath = Join-Path $projectPath 'PHASE2_CREDENTIALS.local.md'
$templateCredentialsPath = Join-Path $projectPath 'PHASE2_CREDENTIALS.md'
$credentialsPath = $null

if (Test-Path $localCredentialsPath) {
    $credentialsPath = $localCredentialsPath
} elseif (Test-Path $templateCredentialsPath) {
    $credentialsPath = $templateCredentialsPath
}

function Get-CredentialValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Key
    )

    if (-not $credentialsPath) {
        return $null
    }

    $pattern = [regex]::Escape($Key) + '=([^`\r\n]+)'
    foreach ($line in Get-Content -Path $credentialsPath) {
        $match = [regex]::Match($line, $pattern)
        if ($match.Success) {
            return $match.Groups[1].Value.Trim()
        }
    }

    return $null
}

function Resolve-Mt5ExpertsPath {
    param(
        [string]$ExplicitPath
    )

    if ($ExplicitPath) {
        if (Test-Path (Join-Path $ExplicitPath 'Black_Knight_Quant_Reporter.mq5')) {
            return $ExplicitPath
        }
    }

    $terminalRoot = Join-Path $env:APPDATA 'MetaQuotes\Terminal'
    if (-not (Test-Path $terminalRoot)) {
        return $null
    }

    Get-ChildItem -Path $terminalRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $candidate = Join-Path $_.FullName 'MQL5\Experts'
        if (Test-Path (Join-Path $candidate 'Black_Knight_Quant_Reporter.mq5')) {
            return $candidate
        }
    }

    return $null
}

$explicitMt5Path = $env:BK_MT5_EXPERTS_PATH
if (-not $explicitMt5Path) {
    $explicitMt5Path = Get-CredentialValue -Key 'BK_MT5_EXPERTS_PATH'
}

$mt5Path = Resolve-Mt5ExpertsPath -ExplicitPath $explicitMt5Path

# 1. Check EA in MT5
Write-Host "[CHECK 1] EA in MT5..." -ForegroundColor Yellow
if ($mt5Path -and (Test-Path (Join-Path $mt5Path 'Black_Knight_Quant_Reporter.mq5'))) {
    $fileInfo = Get-Item (Join-Path $mt5Path 'Black_Knight_Quant_Reporter.mq5')
    Write-Host "  [OK] PASS: EA found ($($fileInfo.Length) bytes)" -ForegroundColor Green
    Write-Host "  Path: $mt5Path" -ForegroundColor Gray
} else {
    Write-Host "  [FAIL] EA not found. Set BK_MT5_EXPERTS_PATH or compile in MT5." -ForegroundColor Red
}

# 2. Check outbox folders
Write-Host "`n[CHECK 2] Outbox folders..." -ForegroundColor Yellow
if (Test-Path "$projectPath\_journal_data\outbox_queue") {
    Write-Host "  [OK] PASS: Outbox queue folder exists" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] Outbox queue folder missing" -ForegroundColor Red
}

if (Test-Path "$projectPath\_journal_data\outbox.db") {
    Write-Host "  [OK] PASS: Outbox database exists" -ForegroundColor Green
} else {
    Write-Host "  [NOTE] Outbox database will be created on first run" -ForegroundColor Cyan
}

# 3. Check credentials
Write-Host "`n[CHECK 3] Credentials..." -ForegroundColor Yellow
if ($credentialsPath) {
    $secret = Get-CredentialValue -Key 'BK_HMAC_SECRET'
    if (-not $secret -or $secret -match '^<ROTATE_ME>$|^ROTATE_ME$') {
        Write-Host "  [FAIL] BK_HMAC_SECRET missing or placeholder" -ForegroundColor Red
    } else {
        Write-Host "  [OK] PASS: Credentials file found" -ForegroundColor Green
    }
    Write-Host "  Path: $credentialsPath" -ForegroundColor Gray
} else {
    Write-Host "  [FAIL] Credentials file not found" -ForegroundColor Red
}

# 4. Check outbox agent script
Write-Host "`n[CHECK 4] Outbox agent..." -ForegroundColor Yellow
if (Test-Path "$projectPath\scratch\phase2_outbox_agent.py") {
    Write-Host "  [OK] PASS: Outbox agent script found" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] Outbox agent not found" -ForegroundColor Red
}

# 5. Check launcher scripts
Write-Host "`n[CHECK 5] Launcher scripts..." -ForegroundColor Yellow
@("RUN_MT5_OUTBOX.bat", "Dashboard.bat", "STOP_TERMINAL.bat") | ForEach-Object {
    if (Test-Path "$projectPath\$_") {
        Write-Host "  [OK] PASS: $_ found" -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] $_ not found" -ForegroundColor Red
    }
}

# 6. Check backend connectivity
Write-Host "`n[CHECK 6] Cloud Backend..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "https://bk-quant-api.onrender.com/health" -Method GET -TimeoutSec 5
    if ($response.status -eq "ok" -or $response.status -eq "online") {
        Write-Host "  [OK] PASS: Backend is online" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] Backend responded but status was '$($response.status)'" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  [FAIL] Backend unreachable or offline" -ForegroundColor Red
    Write-Host "  Details: $($_.Exception.Message)" -ForegroundColor Gray
}

# 7. MT5 Data Folder info
Write-Host "`n[INFO] MT5 Configuration Path:" -ForegroundColor Cyan
if ($mt5Path) {
    Write-Host "  $mt5Path" -ForegroundColor Gray
} else {
    Write-Host "  Not detected. Set BK_MT5_EXPERTS_PATH for accuracy." -ForegroundColor Yellow
}

Write-Host "`n===============================================================" -ForegroundColor Cyan
Write-Host "   SETUP INSTRUCTIONS" -ForegroundColor Cyan
Write-Host "===============================================================`n" -ForegroundColor Cyan

Write-Host "1. COMPILE IN MT5:
   - Open MetaEditor (Tools > MetaEditor)
   - Find: $mt5Path\Black_Knight_Quant_Reporter.mq5
   - Press F5 to compile
   - Or right-click > Compile in terminal`n" -ForegroundColor White

Write-Host "2. LOAD ON CHART:
   - In MT5, open any chart (EURUSD M1 recommended)
   - Insert > Advisors > Advisors
   - Select 'Black_Knight_Quant_Reporter'
   - Allow: Expert Advisors, DLL Imports, Web Requests`n" -ForegroundColor White

Write-Host "3. START OUTBOX AGENT:
   - Run: $projectPath\Dashboard.bat
   - Or: $projectPath\RUN_MT5_OUTBOX.bat`n" -ForegroundColor White

Write-Host "4. VERIFY INTEGRATION:
   - Replace existing EA output path in MT5, ensure it points to: _journal_data/outbox_queue
   - MT5 should write trade JSONs when you close a trade
   - Dashboard should show 'MT5 Connected' status`n" -ForegroundColor White

Write-Host "5. STOP AGENT:
   - Run: $projectPath\STOP_TERMINAL.bat`n" -ForegroundColor White

Write-Host "===============================================================`n" -ForegroundColor Cyan
