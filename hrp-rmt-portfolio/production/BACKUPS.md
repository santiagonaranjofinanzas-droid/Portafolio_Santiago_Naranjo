#TimescaleDB Backups

Automated backups use `pg_dump -Fc` from the TimescaleDB container.

Manual backup:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\backup_timescaledb.ps1 -RetentionDays 30
```

Restore:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\restore_timescaledb.ps1 -BackupFile "C:\path\to\backup.dump"
```

Locations:

- Backups: `backups/timescaledb/*.dump`
- Manifest: `backups/timescaledb/backup_manifest.csv`
- Logs: `logs/backups/`

Windows task:

- `HRP_RMT_TimescaleDB_Backup`
- Schedule: Monday-Friday at 20:00 local time
- Retention: 30 days
