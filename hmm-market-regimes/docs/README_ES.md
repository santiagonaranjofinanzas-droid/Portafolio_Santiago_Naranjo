# Motor de Deteccion de Regimenes de Mercado HMM y Ejecucion

[ [English Version](../README.md) ] | [ Versión en Español ]

---

## Resumen Ejecutivo

> [!NOTE]
> **Objetivo Principal:** Construir un framework cuantitativo de grado institucional para clasificar regímenes latentes de mercado mediante Modelos Ocultos de Markov (HMM) y ejecutar señales en MetaTrader 5 a través de C++/MQL5.

| Dimensión                 | Especificación                                                                  |
| :------------------------ | :------------------------------------------------------------------------------ |
| **Modelo Estocástico**    | Modelo Oculto de Markov (HMM) con Filtro de Hamilton + Salto-Difusión de Merton |
| **Modelo de Volatilidad** | Pronóstico de Varianza Condicional Asimétrica GJR-GARCH(1,1)                    |
| **Motor de Ejecución**    | Expert Advisor C++/MQL5 en MetaTrader 5 con Política Zero-Lag                   |
| **Protocolo Validación**  | Combinatorial Purged Cross-Validation (CPCV) con Purging & Embargo              |
| **Stack Principal**       | Python (Pandas, Arch, Scikit-Learn, SciPy), C++, MQL5, MetaTrader 5             |

---

## Formulación Matemática

Transición de estados bajo la matriz estocástica de Hamilton:

$$P(S_t = j \mid S_{t-1} = i) = p_{ij}$$

Varianza condicional asimétrica mediante GJR-GARCH(1,1):

$$\sigma_t^2 = \omega + (\alpha + \gamma I_{t-1}) \epsilon_{t-1}^2 + \beta \sigma_{t-1}^2$$
