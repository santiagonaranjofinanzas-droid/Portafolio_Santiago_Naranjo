# Motor de Time Series Momentum (TSMOM) y Volatility Targeting

[ [English Version](../README.md) ] | [ Versión en Español ]

---

## Resumen Ejecutivo

> [!NOTE]
> **Objetivo Principal:** Implementar un motor sistemático de seguimiento de tendencia multiactivo con diferenciación fraccional de ventana fija y escalado dinámico de volatilidad.

| Dimensión               | Especificación                                                      |
| :---------------------- | :------------------------------------------------------------------ |
| **Clase de Estrategia** | Time Series Momentum (TSMOM) / Seguimiento de Tendencia             |
| **Estacionariedad**     | Diferenciación Fraccional de Ventana Fija ($d \in [0.3, 0.7]$)      |
| **Control de Riesgo**   | Volatility Targeting (Objetivo de Volatilidad Anualizada Constante) |
| **Stack Principal**     | Python, Pandas, NumPy, Statsmodels, SciPy, Matplotlib               |
