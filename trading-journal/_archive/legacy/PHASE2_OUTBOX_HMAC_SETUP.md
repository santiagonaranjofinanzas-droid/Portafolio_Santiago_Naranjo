#Phase 2 - Outbox + HMAC + Idempotency

This setup keeps MT5-to-cloud ingestion resilient and secure.

##What was implemented

- Backend ingest endpoint now supports:
  - HMAC validation (optional, env-controlled)
  - Event idempotency by `X-BK-Event-Id`
  - Event tracking in `IngestionEvent` table (`received`, `processed`, `error`, `duplicate`)
- Local agent script:
  - `scratch/phase2_outbox_agent.py`
  - Persistent SQLite outbox queue
  - Exponential retry and dead-letter state
  - Optional HMAC signing headers

##1) Backend env vars (Render)

Set these in Render (`bk-quant-api`):

- `BK_INGEST_REQUIRE_HMAC=true`
- `BK_HMAC_SECRET=<ROTATE_ME>`
- `BK_HMAC_KEY_ID=mt5-node-01`
- `BK_HMAC_MAX_SKEW_SECONDS=300`
- `BK_DEFAULT_ORG_ID=1`
- `BK_CORS_ORIGINS=https://black-knight-saas.vercel.app`
- `BK_ENABLE_SOCKET_SERVER=false`

Then redeploy backend.

##2) Local agent env vars

In the machine where the local outbox agent runs (store real values in PHASE2_CREDENTIALS.local.md):

- `BK_AGENT_ENDPOINT=https://bk-quant-api.onrender.com/api/v1/ingest/trade`
- `BK_AGENT_DB_PATH=_journal_data/outbox.db`
- `BK_AGENT_QUEUE_DIR=_journal_data/outbox_queue`
- `BK_AGENT_POLL_SECONDS=2`
- `BK_AGENT_TIMEOUT_SECONDS=10`
- `BK_AGENT_MAX_ATTEMPTS=12`
- `BK_AGENT_BACKOFF_BASE_SECONDS=2`
- `BK_HMAC_SECRET=<ROTATE_ME>`
- `BK_HMAC_KEY_ID=mt5-node-01`

##3) Drop files into queue

The agent imports any `*.json` file from `_journal_data/outbox_queue`.

Example payload:

```json
{
  "position_id": 999002,
  "symbol": "EURUSD",
  "entrytime": "2026-04-14 11:00:00",
  "exittime": "2026-04-14 11:12:00",
  "entryprice": 1.1000,
  "exitprice": 1.1011,
  "gross_pnl": 11.0,
  "commission": -0.7,
  "swap": 0.0,
  "volume": 0.1,
  "type_op": 0,
  "direction": "Buy",
  "exit_reason": 3,
  "netpnl": 10.3,
  "sl": 1.0990,
  "risk_price": 0.0010,
  "valid_sl": true,
  "r_multiple": 1.03
}
```

##4) Run agent

One cycle:

```powershell
python scratch/phase2_outbox_agent.py --once
```

PowerShell launcher with built-in defaults:

```powershell
./scratch/run_phase2_outbox.ps1 -Once
```

Continuous loop:

```powershell
python scratch/phase2_outbox_agent.py
```

Or:

```powershell
./scratch/run_phase2_outbox.ps1
```

##5) Verify

- Agent output should show `[OK] Sent event ...`
- Backend metrics should include new trades:

```powershell
Invoke-RestMethod -Uri "https://bk-quant-api.onrender.com/api/v1/metrics" -Method GET  ConvertTo-Json -Depth 6
```

##6) Idempotency behavior

If the same `X-BK-Event-Id` is sent twice, backend returns:

- `status: duplicate`

No duplicate trade processing occurs.

##7) Rollout strategy

- Start with `BK_INGEST_REQUIRE_HMAC=false` for a short burn-in.
- Confirm agent deliveries and retries.
- Switch to `BK_INGEST_REQUIRE_HMAC=true`.
- Monitor Render logs for signature errors.

See also:

- `PHASE3_PLAN.md`
