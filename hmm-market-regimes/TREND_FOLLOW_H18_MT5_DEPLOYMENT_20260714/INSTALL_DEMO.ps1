[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$TerminalDataPath,

    [Parameter(Mandatory = $true)]
    [switch]$ConfirmDemoAccount
)

$ErrorActionPreference = "Stop"
if (-not $ConfirmDemoAccount) {
    throw "Installation requires -ConfirmDemoAccount. This package is not authorized for live accounts."
}

& (Join-Path $PSScriptRoot "VERIFY_PACKAGE.ps1")

$dataPath = (Resolve-Path -LiteralPath $TerminalDataPath).Path
$mql5 = Join-Path $dataPath "MQL5"
if (-not (Test-Path -LiteralPath $mql5 -PathType Container)) {
    throw "TerminalDataPath does not contain an MQL5 directory: $dataPath"
}

$source = Join-Path $PSScriptRoot "MT5\Experts"
$target = Join-Path $mql5 "Experts\H18_TrendFollow"
New-Item -ItemType Directory -Path $target -Force | Out-Null

foreach ($name in @("H18_TREND10_6001.ex5", "H18_TREND11_6002.ex5")) {
    Copy-Item -LiteralPath (Join-Path $source $name) -Destination (Join-Path $target $name) -Force
}

Write-Output "Installed H18 Trend Follow EAs in: $target"
Write-Output "Refresh MT5 Navigator and attach only on a fresh HEDGING DEMO account."
Write-Output "Keep InpTradingEnabled=false until both runtime parity reports are approved."
Write-Output "For risk incubation attach 6001 and 6002 to two NAS100.fs M15 charts in the SAME demo hedging account."
Write-Output "The EAs share H18_RISK_V1 portfolio limits; do not run unrelated systems in that account."
