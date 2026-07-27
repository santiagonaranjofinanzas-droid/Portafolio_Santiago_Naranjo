#TimescaleDB Persistence Layer

The trading logic remains in the F8 pipeline modules. TimescaleDB is a persistence layer only.

##Start Database

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_timescaledb.ps1
```

Connection:

```text
postgresql://postgres:postgres@localhost:5435/hrp_rmt
```

##Apply Schema / Migrate Existing CSV Data

```powershell
python .\production\migrate_csv_to_timescaledb.py
```

##Check Status

```powershell
python .\production\db_status.py
```

##Daily Sync

The daily pipeline calls:

```powershell
python .\production\sync_daily_to_timescaledb.py --date YYYY-MM-DD
```

after the report is generated. CSV append-only files remain as the audit mirror.
