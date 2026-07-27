# Project detection module

param (
    [string]$projectRoot = "."
)

# Import shared utils using PSScriptRoot
. (Join-Path $PSScriptRoot "..\shared\utils.ps1")

Write-Log "Detecting project technologies in: $projectRoot..."

$results = [ordered]@{
    project_name = (Split-Path $projectRoot -Leaf)
    git = $false
    languages = @()
    frameworks = @()
    project_types = @()
    tools = @()
}

# Helper to check recursive file extensions
function Test-FileExtension ($ext) {
    $files = Get-ChildItem -Path $projectRoot -Filter "*$ext" -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1
    return $null -ne $files
}

# Helper to check content match in files
function Test-FileContent ($pattern, $filter) {
    $match = Get-ChildItem -Path $projectRoot -Filter $filter -Recurse -File -ErrorAction SilentlyContinue | 
             Select-String -Pattern $pattern -SimpleMatch -ErrorAction SilentlyContinue | Select-Object -First 1
    return $null -ne $match
}

# 1. Detect Git
if (Test-Path (Join-Path $projectRoot ".git")) {
    $results.git = $true
}

# 2. Detect Languages
if (Test-FileExtension ".py" -or Test-Path (Join-Path $projectRoot "requirements.txt") -or Test-Path (Join-Path $projectRoot "pyproject.toml")) {
    $results.languages += "python"
}
if (Test-FileExtension ".ts" -or Test-FileExtension ".js" -or Test-Path (Join-Path $projectRoot "package.json")) {
    $results.languages += "typescript"
}
if (Test-FileExtension ".cpp" -or Test-FileExtension ".h" -or Test-Path (Join-Path $projectRoot "CMakeLists.txt")) {
    $results.languages += "cpp"
}
if (Test-FileExtension ".java" -or Test-Path (Join-Path $projectRoot "pom.xml") -or Test-Path (Join-Path $projectRoot "build.gradle")) {
    $results.languages += "java"
}
if (Test-FileExtension ".rs" -or Test-Path (Join-Path $projectRoot "Cargo.toml")) {
    $results.languages += "rust"
}
if (Test-FileExtension ".R" -or Test-FileExtension ".Rmd") {
    $results.languages += "r"
}

# 3. Detect Frameworks
if (Test-FileExtension ".ipynb") {
    $results.frameworks += "jupyter"
}
if (Test-Path (Join-Path $projectRoot "Dockerfile") -or Test-Path (Join-Path $projectRoot "docker-compose.yml")) {
    $results.frameworks += "docker"
}
if (Test-FileContent "fastapi" "*.py") {
    $results.frameworks += "fastapi"
}
if (Test-FileContent "streamlit" "*.py") {
    $results.frameworks += "streamlit"
}

# 4. Detect Typologies
# Quantitative
$isQuant = $false
$quantKeywords = @("trading", "portfolio", "backtest", "histdata", "forex", "crypto", "hmm", "paridades", "xauusd", "nsxusd", "xagusd")
foreach ($kw in $quantKeywords) {
    if (Test-FileContent $kw "*.py" -or Test-FileContent $kw "*.md" -or (Get-ChildItem -Path $projectRoot -Filter "*$kw*" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1)) {
        $isQuant = $true
        break
    }
}
if ($isQuant) {
    $results.project_types += "quantitative"
}

# ML (Machine Learning)
$isML = $false
$mlKeywords = @("torch", "tensorflow", "sklearn", "keras", "model.fit", "training", "dataset")
foreach ($kw in $mlKeywords) {
    if (Test-FileContent $kw "*.py" -or Test-FileContent $kw "*.ipynb") {
        $isML = $true
        break
    }
}
if ($isML) {
    $results.project_types += "ml"
}

# University
$isUni = $false
$uniKeywords = @("tesis", "deberes", "informe", "clases", "universidad", "econometria")
foreach ($kw in $uniKeywords) {
    if (Get-ChildItem -Path $projectRoot -Filter "*$kw*" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1) {
        $isUni = $true
        break
    }
}
if ($isUni) {
    $results.project_types += "university"
}

# Web
$isWeb = $false
if (Test-Path (Join-Path $projectRoot "index.html") -or Test-Path (Join-Path $projectRoot "vite.config.ts") -or Test-Path (Join-Path $projectRoot "next.config.js") -or Test-Path (Join-Path $projectRoot "tailwind.config.js")) {
    $isWeb = $true
}
if ($isWeb) {
    $results.project_types += "web"
}

# 5. Detect System Tools
if (Test-CommandExists "python") { $results.tools += "python" }
if (Test-CommandExists "uv") { $results.tools += "uv" }
if (Test-CommandExists "poetry") { $results.tools += "poetry" }
if (Test-CommandExists "conda") { $results.tools += "conda" }
if (Test-CommandExists "node") { $results.tools += "node" }
if (Test-CommandExists "git") { $results.tools += "git" }
if (Test-CommandExists "docker") { $results.tools += "docker" }
if (Test-CommandExists "rustc") { $results.tools += "rust" }
if (Test-CommandExists "g++") { $results.tools += "cpp" }
if (Test-CommandExists "R") { $results.tools += "r" }

# Output results as JSON
$results | ConvertTo-Json -Depth 5
