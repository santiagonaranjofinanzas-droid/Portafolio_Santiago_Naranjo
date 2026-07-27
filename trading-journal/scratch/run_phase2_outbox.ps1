param(
    [switch]$Once
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not $env:BK_AGENT_ENDPOINT) {
    $env:BK_AGENT_ENDPOINT = 'https://black-knight-backend.onrender.com/api/v1/ingest/trade'
}

if (-not $env:BK_HMAC_SECRET -or $env:BK_HMAC_SECRET -match '^<ROTATE_ME>$|^ROTATE_ME$') {
    throw 'BK_HMAC_SECRET not set. Update PHASE2_CREDENTIALS.local.md before running the agent.'
}

if (-not $env:BK_HMAC_KEY_ID) {
    $env:BK_HMAC_KEY_ID = 'mt5-node-01'
}

if (-not $env:BK_AGENT_QUEUE_DIR) {
    $env:BK_AGENT_QUEUE_DIR = '_journal_data/outbox_queue'
}

if (-not $env:BK_AGENT_DB_PATH) {
    $env:BK_AGENT_DB_PATH = '_journal_data/outbox.db'
}

$queuePaths = $env:BK_AGENT_QUEUE_DIR -split ';'
foreach ($qp in $queuePaths) {
    $qp = $qp.Trim()
    if (-not $qp) { continue }
    if ($qp -notmatch '\*') {
        New-Item -ItemType Directory -Force $qp | Out-Null
    }
}

$agent = Join-Path $projectRoot '.venv\Scripts\python.exe'
$args = @('scratch\phase2_outbox_agent.py')
if ($Once) {
    $args += '--once'
}

$logDir = Join-Path $projectRoot '_journal_data\logs'
New-Item -ItemType Directory -Force $logDir | Out-Null
$logPath = Join-Path $logDir 'outbox_agent.log'

& $agent @args *>> $logPath
