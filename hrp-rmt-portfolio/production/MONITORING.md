#Monitoring API

Read-only FastAPI service for F9 monitoring. It does not change trading logic.

Start:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_monitoring_api.ps1
```

URL:

- http://127.0.0.1:8008/
- http://127.0.0.1:8008/health
- http://127.0.0.1:8008/status
- http://127.0.0.1:8008/weights/latest
- http://127.0.0.1:8008/orders/latest
- http://127.0.0.1:8008/risk/latest
- http://127.0.0.1:8008/nav
- http://127.0.0.1:8008/backup/latest
- http://127.0.0.1:8008/metrics

OpenAPI docs:

- http://127.0.0.1:8008/docs

Startup:

- A shortcut named `HRP_RMT_Monitoring_API.lnk` is placed in the Windows user Startup folder.
- The API is read-only and should remain separate from trading logic.
