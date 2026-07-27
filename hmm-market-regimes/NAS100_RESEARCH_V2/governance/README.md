#Gobierno de investigación NAS100 V2

Este módulo congela el corte de datos, limita el número de candidatos y deja
una cadena de auditoría verificable. El estado inicial ya fue creado en
`state/`; ejecutar `init` otra vez falla de forma intencional.

##Política congelada

- Programa: `NAS100_EDGE_RECOVERY_V2_20260710`.
- Desarrollo: timestamps estrictamente anteriores a
  `2026-07-11T00:00:00Z`.
- Holdout: timestamps mayores o iguales a ese corte.
- Presupuesto: 12 candidatos `TREND_V2` y 9
  `MEAN_REVERSION_V2`.
- Trading real: `LIVE_LOCKED`.
- Todo lo disponible en el sistema anterior está clasificado como
  `DEVELOPMENT_CONSUMED`.

La política íntegra está en
`config/research_preregistration.v1.json`. Su hash canónico es
`4e24f5b6ca091b7931f0ea60f61d84e1c7ece4ab1d4b0978c3552ba96d3b8ea9`.

##Verificación

Desde la raíz del workspace:

```powershell
python -m NAS100_RESEARCH_V2.governance.bootstrap verify
python -m unittest discover -s NAS100_RESEARCH_V2 -p "test_*.py" -v
```

No se debe borrar un archivo `.lock` automáticamente. Su presencia indica que
una escritura pudo interrumpirse y exige revisión manual del ledger antes de
continuar.

##Integración del runner

Un candidato debe registrarse antes de calcular resultados:

```python
from NAS100_RESEARCH_V2.governance.registry import ExperimentRegistry

registry = ExperimentRegistry(
    "NAS100_RESEARCH_V2/governance/state/experiment_registry.jsonl",
    "NAS100_RESEARCH_V2/governance/config/research_preregistration.v1.json",
)
registry.register(
    actor="research_runner",
    experiment_id="TRENDV2.C01",
    model_family="TREND_V2",
    candidate_index=1,
    candidate_config_sha256="<64 hex>",
    canonical_data_manifest_sha256="77c9320b9fc92d7f336f0f283201500c795ed00c6b10cf5be7eaf8fccee1c9da",
    hypothesis="<hipótesis fijada antes de observar el resultado>",
    primary_metric="<métrica primaria fijada>",
)
registry.start(
    actor="research_runner",
    experiment_id="TRENDV2.C01",
    code_identity="git:<commit-or-tree-hash>",
    environment_sha256="<64 hex>",
    random_seed=20260710,
)
```

Al terminar se llama `record_result(...)`; si el proceso no puede producir un
resultado válido se llama `abort(...)`. Un experimento terminal no se reabre.
Una modificación de parámetros consume un índice de candidato nuevo.

Estados admitidos:

```text
REGISTERED -> RUNNING -> COMPLETED
                      -> ABORTED
```

Cada ejecución debe quedar enlazada a:

1. hash de la preregistración;
2. hash de la configuración del candidato;
3. hash del manifiesto canónico de datos;
4. identidad del código;
5. hash del entorno.

##Acceso a datos

`HoldoutAccessController.request_access(...)` debe ejecutarse antes de abrir un
dataset. Las ventanas mixtas siempre se deniegan. Entrenamiento, tuning, EDA y
feature engineering se permiten exclusivamente en desarrollo. El holdout solo
admite `FINAL_EVALUATION` o `FORWARD_MONITORING`, exige un identificador de
autorización y limita la evaluación final a una consulta por combinación
experimento/dataset. Las denegaciones también quedan registradas.

##Propiedades y límites

- La cadena hash detecta edición, inserción, reordenamiento y escrituras
  parciales. `seal()` crea un ancla inmutable y bloquea nuevos eventos.
- Antes del sellado, una eliminación de un sufijo completo y todavía válido
  requiere un ancla externa/WORM para ser detectable. En producción se debe
  exportar periódicamente el `head_hash` a almacenamiento independiente.
- El control de acceso es obligatorio a nivel del runner, pero Python no puede
  impedir que otro proceso abra directamente un parquet. El holdout futuro debe
  protegerse además con ACL separada o almacenamiento de solo lectura concedido
  por el custodio.
- `authorization_id` deja trazabilidad; no autentica por sí solo a una persona.
  La autorización institucional debe existir en el sistema de control de
  accesos externo.
- Los ledgers no son para secretos: actor, hipótesis y métricas quedan en texto
  claro.

