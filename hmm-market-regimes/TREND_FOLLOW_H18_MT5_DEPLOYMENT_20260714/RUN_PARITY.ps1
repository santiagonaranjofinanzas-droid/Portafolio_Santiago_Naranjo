[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Bars,

    [Parameter(Mandatory = $true)]
    [ValidateSet(6001, 6002)]
    [int]$Magic,

    [Parameter(Mandatory = $true)]
    [string]$StartUtc,

    [string]$SignalLog,
    [string]$RiskLog,
    [string]$PythonRiskLog,
    [string]$Output
)

$ErrorActionPreference = "Stop"
if (-not $SignalLog) {
    $SignalLog = Join-Path $env:APPDATA "MetaQuotes\Terminal\Common\Files\H18_${Magic}_signals.csv"
}
if (-not $Output) {
    $Output = Join-Path $PSScriptRoot "Reports\parity_${Magic}.json"
}
if (-not $RiskLog) {
    $RiskLog = Join-Path $env:APPDATA "MetaQuotes\Terminal\Common\Files\H18_${Magic}_risk.csv"
}
if (-not (Test-Path -LiteralPath $Bars -PathType Leaf)) {
    throw "Bars file not found: $Bars"
}
if (-not (Test-Path -LiteralPath $SignalLog -PathType Leaf)) {
    throw "MT5 signal log not found: $SignalLog"
}

$env:PYTHONPATH = Join-Path $PSScriptRoot "PythonReference"
python -c "import numpy, pandas" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Install parity dependencies first: python -m pip install -r requirements-parity.txt"
}

$arguments = @(
    "-m", "NAS100_RESEARCH_V2.deployment.h18_mt5_parity",
    "--bars", $Bars,
    "--mt5-signals", $SignalLog,
    "--magic", $Magic,
    "--start-utc", $StartUtc,
    "--output", $Output
)
if (Test-Path -LiteralPath $RiskLog -PathType Leaf) {
    $arguments += @("--mt5-risk", $RiskLog)
}
if ($PythonRiskLog) {
    if (-not (Test-Path -LiteralPath $RiskLog -PathType Leaf)) { throw "MT5 risk log not found: $RiskLog" }
    if (-not (Test-Path -LiteralPath $PythonRiskLog -PathType Leaf)) { throw "Python risk log not found: $PythonRiskLog" }
    $arguments += @("--python-risk", $PythonRiskLog)
}
python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Parity audit failed for magic $Magic"
}
Write-Output "Parity report: $Output"
