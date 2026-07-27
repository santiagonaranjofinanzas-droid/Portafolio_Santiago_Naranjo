# Framework CLI Controller
# Usage: ./framework.ps1 <command> [arguments]

param (
    [string]$Command = "",
    [string]$Argument = ""
)

# Set UTF-8 encoding
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$workspaceDir = $PSScriptRoot
$utilsPath = Join-Path $workspaceDir ".agents\scripts\utils.ps1"

if (Test-Path $utilsPath) {
    . $utilsPath
} else {
    function Write-Log ($m) { Write-Output "[INFO] $m" }
    function Write-Success ($m) { Write-Output "[SUCCESS] $m" }
    function Write-Warning ($m) { Write-Output "[WARNING] $m" }
    function Write-Error ($m) { Write-Output "[ERROR] $m" }
}

# Load framework metadata
$frameworkJsonPath = Join-Path $workspaceDir "framework.json"
if (Test-Path $frameworkJsonPath) {
    $metadata = Get-Content $frameworkJsonPath -Raw | ConvertFrom-Json
} else {
    $metadata = $null
}

if ([string]::IsNullOrEmpty($Command)) {
    Write-Output "AI Development Framework CLI"
    if ($metadata) {
        Write-Output "Version: $($metadata.framework_version)"
    }
    Write-Output "`nUsage: ./framework.ps1 <command>"
    Write-Output "Commands:"
    Write-Output "  doctor     - Diagnose and check the project environment health"
    Write-Output "  audit      - Run a detailed audit and generate PROJECT_AUDIT_REPORT.md"
    Write-Output "  update     - Update framework scripts and templates"
    Write-Output "  quant      - Initialize Quantitative/ML modules and folder structure"
    exit 0
}

# Helper to print check results
function Print-Check ($success, $message, $warning = $false) {
    $okChar = [char]0x2714
    $warnChar = [char]0x26A0
    $errChar = [char]0x274C
    
    if ($success) {
        if ($Host.UI.RawUI) {
            Write-Host " [$okChar] $message" -ForegroundColor Green
        } else {
            Write-Output " [$okChar] $message"
        }
    } elseif ($warning) {
        if ($Host.UI.RawUI) {
            Write-Host " [$warnChar] $message" -ForegroundColor Yellow
        } else {
            Write-Output " [$warnChar] $message"
        }
    } else {
        if ($Host.UI.RawUI) {
            Write-Host " [$errChar] $message" -ForegroundColor Red
        } else {
            Write-Output " [$errChar] $message"
        }
    }
}

# --- COMMANDS ---

if ($Command -eq "doctor") {
    Write-Output "=== Framework Doctor ==="
    
    # 1. Check Git
    $gitOk = Get-Command git -ErrorAction SilentlyContinue
    Print-Check ($null -ne $gitOk) "Git: $(if ($gitOk) { 'Available' } else { 'Missing' })"
    
    if ($gitOk) {
        $gitStatus = & git status --porcelain 2>&1
        $untracked = ($gitStatus | Select-String -Pattern "^\?\?")
        $modified = ($gitStatus | Select-String -Pattern "^[MADRC]")
        Print-Check ($untracked.Count -eq 0) "No untracked files in Git (Found: $($untracked.Count))" ($untracked.Count -gt 0)
        Print-Check ($modified.Count -eq 0) "No uncommitted modifications in Git (Found: $($modified.Count))" ($modified.Count -gt 0)
    }

    # 2. Check Python & UV
    $pythonOk = Get-Command python -ErrorAction SilentlyContinue
    Print-Check ($null -ne $pythonOk) "Python: $(if ($pythonOk) { 'Available' } else { 'Missing' })"
    
    $uvOk = Get-Command uv -ErrorAction SilentlyContinue
    Print-Check ($null -ne $uvOk) "uv tool: $(if ($uvOk) { 'Available' } else { 'Missing' })" ($null -eq $uvOk)

    # 3. Check Serena
    $serenaOk = Get-Command serena -ErrorAction SilentlyContinue
    Print-Check ($null -ne $serenaOk) "Serena LSP: $(if ($serenaOk) { 'Available' } else { 'Missing' })"
    
    if ($serenaOk) {
        $serenaHealth = & serena project health-check 2>&1
        $serenaPassed = ($LASTEXITCODE -eq 0)
        Print-Check $serenaPassed "Serena tools indexing check"
    }

    # 4. Check Graphify
    $graphifyOk = Get-Command graphify -ErrorAction SilentlyContinue
    Print-Check ($null -ne $graphifyOk) "Graphify: $(if ($graphifyOk) { 'Available' } else { 'Missing' })"
    
    $graphJson = Join-Path $workspaceDir "graphify-out\graph.json"
    Print-Check (Test-Path $graphJson) "Graphify knowledge graph index exists"

    # 5. Check Documentation
    $docsList = @("README.md", "docs\ARCHITECTURE.md", "docs\SETUP.md", "docs\DECISIONS.md")
    foreach ($doc in $docsList) {
        $docPath = Join-Path $workspaceDir $doc
        Print-Check (Test-Path $docPath) "Doc: $doc exists"
    }
    
    exit 0
}

elseif ($Command -eq "audit") {
    Write-Output "Generating PROJECT_AUDIT_REPORT.md..."
    
    $reportPath = Join-Path $workspaceDir "PROJECT_AUDIT_REPORT.md"
    
    # Gathering audit data
    $gitOk = Get-Command git -ErrorAction SilentlyContinue
    $pythonOk = Get-Command python -ErrorAction SilentlyContinue
    $serenaOk = Get-Command serena -ErrorAction SilentlyContinue
    $graphifyOk = Get-Command graphify -ErrorAction SilentlyContinue
    
    $gitStatusReport = "Not available"
    if ($gitOk) {
        $gitStatusReport = (& git status 2>&1).ToString()
    }
    
    $serenaStatusReport = "Not available"
    if ($serenaOk) {
        $serenaStatusReport = "Installed in system"
    }
    
    $graphifyStats = "No index"
    $graphJson = Join-Path $workspaceDir "graphify-out\graph.json"
    if (Test-Path $graphJson) {
        $graphObj = Get-Content $graphJson -Raw | ConvertFrom-Json
        $nodesCount = if ($graphObj.nodes) { $graphObj.nodes.Count } else { 0 }
        $edgesCount = if ($graphObj.edges) { $graphObj.edges.Count } else { 0 }
        $graphifyStats = "Nodes: $nodesCount, Edges: $edgesCount"
    }
    
    # Cobertura de Docs
    $docsList = @("README.md", "README_AGENT.md", "docs\README.md", "docs\ARCHITECTURE.md", "docs\SETUP.md", "docs\DECISIONS.md", "docs\AI_GUIDELINES.md")
    $docsTable = ""
    foreach ($doc in $docsList) {
        $exists = Test-Path (Join-Path $workspaceDir $doc)
        $docsTable += "| $doc | $(if ($exists) { '✔ Exists' } else { '❌ Missing' }) |`n"
    }

    $reportContent = @"
# Project Audit Report

Generated on: $((Get-Date).ToString("yyyy-MM-dd HH:mm:ss"))
Framework Version: $(if ($metadata) { $metadata.framework_version } else { "Unknown" })

## Development Tools
| Tool | Available | Path |
| --- | --- | --- |
| Git | $(if ($gitOk) { '✔ Yes' } else { '❌ No' }) | $(if ($gitOk) { (Get-Command git).Source } else { 'N/A' }) |
| Python | $(if ($pythonOk) { '✔ Yes' } else { '❌ No' }) | $(if ($pythonOk) { (Get-Command python).Source } else { 'N/A' }) |
| Serena | $(if ($serenaOk) { '✔ Yes' } else { '❌ No' }) | $(if ($serenaOk) { (Get-Command serena).Source } else { 'N/A' }) |
| Graphify | $(if ($graphifyOk) { '✔ Yes' } else { '❌ No' }) | $(if ($graphifyOk) { (Get-Command graphify).Source } else { 'N/A' }) |

## Git Status
```text
$gitStatusReport
```

## Knowledge Graphs & Indices
- **Serena Status:** $serenaStatusReport
- **Graphify Stats:** $graphifyStats

## Documentation Coverage
| Document | Status |
| --- | --- |
$docsTable
"@
    [System.IO.File]::WriteAllText($reportPath, $reportContent, [System.Text.Encoding]::UTF8)
    Write-Success "Audit completed! Report saved to PROJECT_AUDIT_REPORT.md."
    exit 0
}

elseif ($Command -eq "update") {
    if (!$metadata -or [string]::IsNullOrEmpty($metadata.template_path)) {
        Write-Error "Framework metadata is corrupted or missing template_path in framework.json."
        exit 1
    }
    
    $templateDir = $metadata.template_path
    if (!(Test-Path $templateDir)) {
        Write-Error "Template path not found: $templateDir. Update aborted."
        exit 1
    }
    
    $templateMetaPath = Join-Path $templateDir "framework.json"
    if (!(Test-Path $templateMetaPath)) {
        Write-Error "Template framework.json missing in $templateDir."
        exit 1
    }
    
    $templateMeta = Get-Content $templateMetaPath -Raw | ConvertFrom-Json
    Write-Output "Current version: $($metadata.framework_version)"
    Write-Output "Latest version:  $($templateMeta.framework_version)"
    
    if ($metadata.framework_version -eq $templateMeta.framework_version -and $Argument -ne "--force") {
        Write-Success "Framework is up to date."
        exit 0
    }
    
    Write-Output "Updating framework components..."
    
    # 1. Update framework.json
    $metadata.framework_version = $templateMeta.framework_version
    $metadata | ConvertTo-Json | Out-File $frameworkJsonPath -Encoding utf8
    
    # 2. Copy scripts
    $targetScriptsDir = Join-Path $workspaceDir ".agents\scripts"
    $srcScriptsDir = Join-Path $templateDir "scripts"
    if (Test-Path $srcScriptsDir) {
        Get-ChildItem -Path $srcScriptsDir -Filter "*.ps1" -File | ForEach-Object {
            Copy-Item $_.FullName (Join-Path $targetScriptsDir $_.Name) -Force
        }
        # Copy utils
        Copy-Item (Join-Path $templateDir "shared\utils.ps1") (Join-Path $targetScriptsDir "utils.ps1") -Force
    }
    
    # 3. Copy CLI wrappers
    Copy-Item (Join-Path $templateDir "framework.ps1") (Join-Path $workspaceDir "framework.ps1") -Force
    Copy-Item (Join-Path $templateDir "framework.bat") (Join-Path $workspaceDir "framework.bat") -Force
    
    # 4. Copy startup templates
    Copy-Item (Join-Path $templateDir "templates\antigravity\startup.bat") (Join-Path $workspaceDir ".agents\startup.bat") -Force
    Copy-Item (Join-Path $templateDir "templates\antigravity\startup.ps1") (Join-Path $workspaceDir ".agents\startup.ps1") -Force
    
    Write-Success "Framework successfully updated to version $($templateMeta.framework_version)!"
    exit 0
}

elseif ($Command -eq "quant") {
    Write-Output "Initializing Quantitative/ML Module..."
    
    # 1. Create folders
    $dirs = @("data\raw", "data\processed", "experiments", "backtests", "models")
    foreach ($d in $dirs) {
        $path = Join-Path $workspaceDir $d
        if (!(Test-Path $path)) {
            New-Item -ItemType Directory -Path $path -Force | Out-Null
            Write-Output "Created directory: $d"
        }
    }
    
    # 2. Copy files from templates
    if ($metadata -and (Test-Path $metadata.template_path)) {
        $templateDir = $metadata.template_path
        $quantSrcDir = Join-Path $templateDir "templates\quant"
        
        if (Test-Path $quantSrcDir) {
            $filesToCopy = @("quant_utils.py", "backtest_config.json", "run_experiment.py")
            foreach ($file in $filesToCopy) {
                $dest = Join-Path $workspaceDir $file
                if (!(Test-Path $dest)) {
                    Copy-Item (Join-Path $quantSrcDir $file) $dest -Force
                    Write-Output "Created file: $file"
                } else {
                    Write-Warning "File already exists, skipping: $file"
                }
            }
            Write-Success "Quantitative/ML Module initialized successfully."
        } else {
            Write-Error "Quantitative templates not found at $quantSrcDir."
        }
    } else {
        Write-Error "Framework template path is not accessible. Cannot fetch templates."
    }
    exit 0
}

else {
    Write-Error "Unknown command: $Command"
    exit 1
}
