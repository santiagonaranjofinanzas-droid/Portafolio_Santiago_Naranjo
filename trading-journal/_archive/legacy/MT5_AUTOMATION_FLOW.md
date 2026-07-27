#MT5 Automation Flow

This is the operating path now:

1. MT5 EA writes trade snapshots into `_journal_data/outbox_queue` as JSON files.
2. `scratch/run_phase2_outbox_from_md.ps1` loads local credentials from `PHASE2_CREDENTIALS.local.md`.
3. `scratch/run_phase2_outbox.ps1` imports queued files, signs them, and sends them to Render.
4. Render persists the trade in Postgres and marks the ingestion event as processed.
5. The frontend reads `GET /api/v1/metrics` from Render.
6. The dashboard reflects the new trades automatically.

##Local launchers

- `Dashboard.bat` opens the cloud dashboard and launches the MT5 outbox agent hidden.
- `STOP_TERMINAL.bat` stops the outbox agent and any leftover local listeners.

##Important constraints

- `BK_HMAC_SECRET` must match between Render and local credentials exactly.
- `BK_HMAC_KEY_ID` must match between Render and local credentials exactly.
- Do not commit `PHASE2_CREDENTIALS.local.md`.
