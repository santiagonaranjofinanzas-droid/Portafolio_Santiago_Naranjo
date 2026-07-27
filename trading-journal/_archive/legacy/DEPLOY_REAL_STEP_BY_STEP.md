#Despliegue real paso a paso (Fase 1)

Este runbook despliega:

- Frontend en Vercel
- Backend en Render (plan Free para iniciar)
- Base de datos Postgres en Neon

##0) Prechecks locales

1. Confirma que tu frontend lee API por variable de entorno (`NEXT_PUBLIC_API_BASE_URL`).
2. Confirma que backend soporta `BK_DATABASE_URL` y `BK_CORS_ORIGINS`.
3. Ten una cuenta activa en:
   - Neon
   - Render
   - Vercel

##1) Crear base de datos en Neon

1. En Neon crea un proyecto nuevo.
2. Copia la cadena de conexión Postgres (URI completa).
3. Cambia esquema si quieres (opcional), pero para inicio usa `public`.

Resultado esperado:

- Tienes un valor para `BK_DATABASE_URL`, por ejemplo:
  - `postgresql+psycopg://user:pass@host/dbname?sslmode=require`

Nota:

- Si Neon te da `postgresql://...`, el backend lo normaliza automáticamente.

##2) Desplegar backend en Render

Este repo ya incluye `render.yaml`.

1. En Render: New + Blueprint.
2. Conecta este repositorio.
3. Render detecta `render.yaml` y crea el servicio `bk-quant-api`.
4. Antes de desplegar, configura variables:
   - `BK_DATABASE_URL` = URI de Neon
   - `BK_CORS_ORIGINS` = dominio de frontend Vercel (temporalmente puedes usar `*`)
5. Ejecuta deploy.

Resultado esperado:

- Servicio `bk-quant-api` con URL pública, por ejemplo:
  - `https://bk-quant-api.onrender.com`
- `GET /health` responde 200

Prueba rápida desde PowerShell:

```powershell
Invoke-RestMethod -Uri "https://TU_BACKEND.onrender.com/health" -Method GET
```

##3) Desplegar frontend en Vercel

1. En Vercel: Add New Project.
2. Selecciona este repositorio.
3. En Root Directory elige `frontend`.
4. En Environment Variables agrega:
   - `NEXT_PUBLIC_API_BASE_URL` = `https://TU_BACKEND.onrender.com/api/v1`
5. Deploy.

Resultado esperado:

- URL pública de frontend en Vercel.
- El dashboard carga métricas desde backend cloud.

##4) Ajustar CORS final en backend

1. Vuelve a Render y edita `BK_CORS_ORIGINS`.
2. Usa solo tu dominio real de Vercel, por ejemplo:
   - `https://tu-frontend.vercel.app`
3. Redeploy backend.

##5) Verificación end-to-end

##5.1 Health backend

```powershell
Invoke-RestMethod -Uri "https://TU_BACKEND.onrender.com/health" -Method GET
```

##5.2 Métricas

```powershell
Invoke-RestMethod -Uri "https://TU_BACKEND.onrender.com/api/v1/metrics" -Method GET
```

##5.3 Ingesta de prueba

```powershell
$body = @{
  position_id = 999001
  symbol = "EURUSD"
  entrytime = "2026-04-14 10:00:00"
  exittime = "2026-04-14 10:10:00"
  entryprice = 1.1000
  exitprice = 1.1010
  gross_pnl = 10.0
  commission = -0.7
  swap = 0.0
  volume = 0.1
  type_op = 0
  direction = "Buy"
  exit_reason = 3
  netpnl = 9.3
  sl = 1.0990
  risk_price = 0.0010
  valid_sl = $true
  r_multiple = 1.0
}  ConvertTo-Json

Invoke-RestMethod -Uri "https://TU_BACKEND.onrender.com/api/v1/ingest/trade" -Method POST -ContentType "application/json" -Body $body
```

Luego revisa:

```powershell
Invoke-RestMethod -Uri "https://TU_BACKEND.onrender.com/api/v1/metrics" -Method GET
```

##6) Conectar MT5 real a cloud

1. En tu EA MT5 cambia URL de ingesta hacia backend cloud:
   - `https://TU_BACKEND.onrender.com/api/v1/ingest/trade`
2. Mantén tu flujo local para envío de trades.
3. Verifica en logs de Render que llegan eventos.

##7) Riesgos del plan Free (importante)

- Render Free puede suspender/hibernar en idle.
- Si quieres continuidad 24/7 para API, migra backend a Oracle Always Free VM.

##8) Paso siguiente recomendado

Cuando este flujo esté estable, avanzar a Fase 2:

- Agent local con outbox persistente
- Firma HMAC
- Idempotencia por evento
- Reintentos automáticos

Runbook de implementación:

- `PHASE2_OUTBOX_HMAC_SETUP.md`
