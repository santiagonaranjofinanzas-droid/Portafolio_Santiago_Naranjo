param(
    [Parameter(Mandatory = $true)]
    [string]$TerminalDataPath
)

$ErrorActionPreference = "Stop"
$source = Join-Path $PSScriptRoot "Experts"
$mql5 = Join-Path $TerminalDataPath "MQL5"
if (-not (Test-Path $mql5)) {
    throw "TerminalDataPath does not contain MQL5: $TerminalDataPath"
}
$target = Join-Path $mql5 "Experts\H18_Demo"
New-Item -ItemType Directory -Path $target -Force | Out-Null

foreach ($name in @("H18_TREND10_6001.ex5", "H18_TREND11_6002.ex5")) {
    $artifact = Join-Path $source $name
    if (-not (Test-Path $artifact)) {
        throw "Compiled artifact missing: $artifact"
    }
    Copy-Item -LiteralPath $artifact -Destination (Join-Path $target $name) -Force
}

Write-Output "Installed demo-only H18 EAs to $target"
Write-Output "Restart/refresh Navigator, then attach each EA to its own NAS100.fs M15 chart on a hedging DEMO account."
Write-Output "Use the same isolated demo account for both EAs so the shared portfolio risk cap is exercised."
