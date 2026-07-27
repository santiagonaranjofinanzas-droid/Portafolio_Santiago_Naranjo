param(
    [switch]$Once
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$localCredentialsPath = Join-Path $projectRoot 'PHASE2_CREDENTIALS.local.md'
$templateCredentialsPath = Join-Path $projectRoot 'PHASE2_CREDENTIALS.md'

if (Test-Path $localCredentialsPath) {
    $credentialsPath = $localCredentialsPath
} elseif (Test-Path $templateCredentialsPath) {
    $credentialsPath = $templateCredentialsPath
} else {
    throw "Missing credentials file. Create PHASE2_CREDENTIALS.local.md from the template."
}

function Get-CredentialValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Key
    )

    $pattern = [regex]::Escape($Key) + '=([^`\r\n]+)'
    foreach ($line in Get-Content -Path $credentialsPath) {
        $match = [regex]::Match($line, $pattern)
        if ($match.Success) {
            return $match.Groups[1].Value.Trim()
        }
    }

    return $null
}

$env:BK_AGENT_ENDPOINT = (Get-CredentialValue -Key 'BK_AGENT_ENDPOINT')
if (-not $env:BK_AGENT_ENDPOINT) {
    $env:BK_AGENT_ENDPOINT = 'https://black-knight-backend.onrender.com/api/v1/ingest/trade'
}

$env:BK_HMAC_SECRET = (Get-CredentialValue -Key 'BK_HMAC_SECRET')
$env:BK_HMAC_KEY_ID = (Get-CredentialValue -Key 'BK_HMAC_KEY_ID')

if (-not $env:BK_HMAC_SECRET -or $env:BK_HMAC_SECRET -match '^<ROTATE_ME>$|^ROTATE_ME$') {
    throw 'BK_HMAC_SECRET missing or placeholder. Update PHASE2_CREDENTIALS.local.md with a real value.'
}

if (-not $env:BK_HMAC_KEY_ID) {
    $env:BK_HMAC_KEY_ID = 'mt5-node-01'
}

$env:BK_AGENT_QUEUE_DIR = (Get-CredentialValue -Key 'BK_AGENT_QUEUE_DIR')
if (-not $env:BK_AGENT_QUEUE_DIR) {
    $env:BK_AGENT_QUEUE_DIR = '_journal_data/outbox_queue'
}

$env:BK_AGENT_DB_PATH = (Get-CredentialValue -Key 'BK_AGENT_DB_PATH')
if (-not $env:BK_AGENT_DB_PATH) {
    $env:BK_AGENT_DB_PATH = '_journal_data/outbox.db'
}

$queuePaths = $env:BK_AGENT_QUEUE_DIR -split ';'
foreach ($qp in $queuePaths) {
    $qp = $qp.Trim()
    if (-not $qp) { continue }
    try {
        $isRooted = [System.IO.Path]::IsPathRooted($qp)
    } catch {
        $isRooted = $false
    }
    if (-not $isRooted) {
        $qp = Join-Path $projectRoot $qp
    }
    if ($qp -notmatch '\*') {
        New-Item -ItemType Directory -Force $qp | Out-Null
    }
}

if ($Once) {
    & (Join-Path $projectRoot 'scratch\run_phase2_outbox.ps1') -Once
} else {
    & (Join-Path $projectRoot 'scratch\run_phase2_outbox.ps1')
}
