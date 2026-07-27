#Dataset canónico Axi NAS100 V2

`axi_qa.py` consume únicamente las particiones Axi bajo `year=/month=` del
sistema anterior, sin modificarlas. Las copias parquet duplicadas del nivel
superior no entran en el dataset.

##Resultado fijado

- Fuente: 15 archivos, 7,814,606 ticks Bid/Ask.
- Hash del conjunto fuente:
  `38c10cc1b9ae75fb1e42d017d84ed17433b85c5eae3881254f167d069325e00f`.
- Barras M15 completas: 1,300 de 1,300 esperadas; cobertura 100%.
- Se excluyó de forma explícita la barra parcial final de las 08:00 UTC.
- Quotes inválidas, cruzadas, bloqueadas, duplicadas, fuera de orden o fuera de
  la grilla: 0.
- Gaps activos mayores a 30 segundos: 0.
- Racha máxima sin cambio de Bid/Ask: 11.817 segundos.
- Spread: mediana 2.50, p95 3.00, p99 3.50, máximo 16.75.
- Paridad con las 1,300 barras Bid heredadas: 0 celdas OHLC distintas.
- Dictamen QA: `PASS`.

El artefacto que todo runner debe consumir es
`artifacts/NAS100_fs_M15_DEVELOPMENT_CANONICAL.parquet`. La identidad que debe
registrarse es el campo `manifest_sha256` de
`artifacts/canonical_data_manifest.json`:

```text
77c9320b9fc92d7f336f0f283201500c795ed00c6b10cf5be7eaf8fccee1c9da
```

##Verificación sin reescribir

```powershell
python -m NAS100_RESEARCH_V2.data_tools.axi_qa verify `
  --manifest NAS100_RESEARCH_V2/data_tools/artifacts/canonical_data_manifest.json
```

El auditor no sobrescribe artefactos. Una nueva captura o un calendario
distinto requiere una configuración versionada y un directorio de salida
nuevo.

##Esquema de barras

El índice es `timestamp_utc`. Las columnas son:

- `bid_open`, `bid_high`, `bid_low`, `bid_close`;
- `ask_open`, `ask_high`, `ask_low`, `ask_close`;
- `spread_median`, `spread_p95`, `spread_max`;
- `tick_count`, `first_tick_utc`, `last_tick_utc`.

Solo se incluyen slots M15 completos del calendario registrado. Los timestamps
originales eran `datetime64[ns]` sin timezone; se interpretan como UTC porque
ese es el contrato explícito del capturador MT5. Esta suposición queda fijada en
la configuración y debe revisarse si cambia la fuente.

La aprobación QA certifica integridad y cobertura de esta muestra corta; no
demuestra edge, robustez estadística ni aptitud para trading real.

