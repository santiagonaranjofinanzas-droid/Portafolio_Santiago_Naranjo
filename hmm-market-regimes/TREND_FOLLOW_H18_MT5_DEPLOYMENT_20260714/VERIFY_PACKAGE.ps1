[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$manifestPath = Join-Path $PSScriptRoot "SHA256SUMS.csv"
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "Missing checksum manifest: $manifestPath"
}

$failed = @()
foreach ($item in (Import-Csv -LiteralPath $manifestPath)) {
    $path = Join-Path $PSScriptRoot $item.Path
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        $failed += "MISSING: $($item.Path)"
        continue
    }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $item.SHA256.ToLowerInvariant()) {
        $failed += "HASH MISMATCH: $($item.Path)"
    }
}

if ($failed.Count -gt 0) {
    throw ("Package verification failed:`n" + ($failed -join "`n"))
}
Write-Output "Package verification passed: all listed files match SHA-256."
