#Roadmap Pendiente de Despliegue

Estado actual: F8/F9 técnico parcial operativo.

El sistema ya cuenta con:

- Pipeline diario F8 programado en Windows.
- Tiingo como proveedor primario V1.
- TimescaleDB activo en Docker.
- Sincronización CSV -> TimescaleDB.
- Backups automáticos de TimescaleDB.
- FastAPI read-only para monitoring.
- Dashboard local y endpoint `/metrics`.
- Configuración de trading congelada.
- Regla institucional intacta: cálculo diario, ejecución ordinaria mensual.

El siguiente trabajo debe enfocarse en robustez operativa, seguridad y transición ordenada hacia paper trading institucional. No se deben cambiar parámetros del modelo durante esta fase.

---

#1. Seguridad y Secretos

##Pendiente

- Cambiar credenciales por defecto de TimescaleDB.
- Rotar `POSTGRES_PASSWORD` en `.env`.
- Restringir acceso de TimescaleDB a `localhost` si no se requiere acceso externo.
- Crear usuario read-only para FastAPI.
- Crear usuario writer separado para sync diario.
- Evitar que FastAPI use credenciales admin.

##Criterio de aceptación

- `postgres` no es usado por la API.
- La API solo puede ejecutar `SELECT`.
- El sync diario usa un usuario con permisos `INSERT/UPDATE` limitados.
- `.env` sigue fuera de Git.

---

#2. Backups y Restore

##Pendiente

- Probar restore completo en una base temporal.
- Registrar evidencia de restore exitoso.
- Añadir backup semanal fuera de la máquina local.
- Validar que el manifiesto de backups no crezca sin control.

##Criterio de aceptación

- Se puede restaurar `hrp_rmt` desde un `.dump`.
- El restore reconstruye hypertables y datos.
- El hash SHA-256 del backup queda registrado.
- Existe al menos una copia fuera del equipo principal.

---

#3. Monitoring Operativo

##Pendiente

- Añadir alertas visuales en dashboard cuando:
  - pipeline != OK;
  - risk != OK;
  - backup missing;
  - tracking error > umbral;
  - no hay datos nuevos del día esperado.
- Añadir endpoint `/alerts`.
- Añadir endpoint `/coverage`.
- Añadir endpoint `/calendar/next-rebalance`.
- Añadir tabla de últimos reportes diarios.

##Criterio de aceptación

- El dashboard permite detectar en menos de 30 segundos si el sistema está operable.
- `/metrics` puede ser consumido por Prometheus o equivalente.
- Las alertas no escriben órdenes ni modifican estado de trading.

---

#4. Scheduler y Operación Diaria

##Pendiente

- Confirmar durante varios días que `HRP_RMT_F8_Daily` corre a las 18:30.
- Confirmar que Tiingo ya publicó datos EOD a esa hora.
- Si Tiingo no publica a tiempo, mover tarea a 19:30 o 20:30.
- Añadir retry controlado si falta algún ticker.
- Añadir resumen automático post-run.

##Criterio de aceptación

- 10 ejecuciones consecutivas sin intervención manual.
- 0 duplicados operativos.
- 0 órdenes fuera de regla.
- Logs diarios completos.

---

#5. Calidad de Datos

##Pendiente

- Endurecer `quality_gate.py`:
  - retornos extremos;
  - stale prices multi-día;
  - splits/dividendos anormales;
  - gaps por calendario;
  - volumen cero persistente;
  - validación de OHLC ajustado/no ajustado.
- Generar reporte diario de ETFs missing/stale.
- Separar warnings no bloqueantes de bloqueos críticos.

##Criterio de aceptación

- El pipeline bloquea generación de órdenes ante datos críticos.
- Los missing no se rellenan silenciosamente.
- Todo bloqueo queda registrado en TimescaleDB y CSV.

---

#6. Ledger y Paper Trading

##Pendiente

- Mejorar cálculo de NAV con precios reales diarios.
- Calcular PnL diario por posición.
- Calcular costos estimados por orden con spreads/proxies más realistas.
- Registrar fills simulados con precio estimado.
- Implementar cash ledger completo.
- Calcular tracking error acumulado.

##Criterio de aceptación

- `portfolio_nav` refleja cambios diarios de mercado.
- `positions` y `cash` reconcilian con NAV.
- Las órdenes simuladas producen fills simulados auditables.
- No hay edición histórica silenciosa.

---

#7. OMS y Reglas de Ejecución

##Pendiente

- Probar caso month-end real o simulado.
- Probar buffer del 3%.
- Probar `RISK_REDUCTION` cuando `sigma_forecast > 18%`.
- Probar `DATA_BLOCK`.
- Probar kill switch manual.
- Añadir tests de no-rebalanceo diario.

##Criterio de aceptación

- En días normales no month-end: `NO_TRADE`.
- En month-end con turnover < 3%: `NO_TRADE`.
- En month-end con turnover >= 3%: `MONTH_END_REBALANCE`.
- Ante riesgo extremo: `RISK_REDUCTION`.
- Ante datos malos: `DATA_BLOCK`.

---

#8. Tests Automatizados F9

##Pendiente

- Añadir tests para:
  - conexión TimescaleDB;
  - migración idempotente;
  - sync diario idempotente;
  - endpoints FastAPI;
  - backup manifest;
  - lectura read-only de API;
  - no alteración de lógica de trading.

##Criterio de aceptación

- `pytest` cubre módulos nuevos de `production/`.
- La migración puede ejecutarse dos veces sin duplicar datos críticos.
- API responde `/health`, `/status`, `/weights/latest`, `/metrics`.

---

#9. Documentación Operativa

##Pendiente

- Crear runbook:
  - qué revisar cada mañana;
  - qué hacer si falla Tiingo;
  - qué hacer si falla TimescaleDB;
  - qué hacer si falla backup;
  - cómo restaurar;
  - cómo pausar la tarea diaria;
  - cómo reanudar.
- Crear checklist diario F8/F9.
- Crear checklist de cierre mensual.

##Criterio de aceptación

- Cualquier operador puede diagnosticar estado básico sin leer código.
- El procedimiento de restore está documentado y probado.

---

#10. Paper Broker / Broker API

##Pendiente

- Elegir broker paper.
- Crear `paper_broker_adapter.py`.
- Separar órdenes simuladas internas de órdenes paper broker.
- Comparar fill simulado vs fill paper.
- Medir slippage real/paper.

##Criterio de aceptación

- Paper broker conectado sin capacidad de operar capital real.
- No hay órdenes duplicadas.
- Fill ratio simulado > 98%.
- Execution tracking error < 0.50%.

---

#11. Antes de Capital Real

##Pendiente

- 60 días hábiles de F8/F9 sin fallos críticos.
- Restore probado.
- Backups externos.
- Usuario DB no-admin.
- API read-only validada.
- Kill switch probado.
- Month-end rebalance probado.
- Revisión humana independiente.

##Criterio de aceptación

- Fallos críticos de datos = 0.
- Órdenes duplicadas = 0.
- Logs reproducibles = 100%.
- Tracking error acumulado < 1.00%.
- Costos simulados dentro del escenario base.
- Aprobación documentada.

---

#Próximo Paso Recomendado

El siguiente paso inmediato es:

1. Rotar credenciales de TimescaleDB.
2. Crear usuarios `hrp_readonly` y `hrp_writer`.
3. Hacer que FastAPI use `hrp_readonly`.
4. Hacer que el sync diario use `hrp_writer`.
5. Probar restore en una base temporal.

Esto fortalece la seguridad y la recuperabilidad sin tocar la lógica de trading.
