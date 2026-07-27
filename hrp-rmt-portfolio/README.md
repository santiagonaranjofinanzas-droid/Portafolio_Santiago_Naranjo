# Hierarchical Risk Parity (HRP) & Random Matrix Theory (RMT) Portfolio Construction

[ English ] | [ [Versión en Español](docs/README_ES.md) ]

---

## Executive Summary

> [!NOTE]
> **Core Objective:** Build a robust portfolio optimization framework that eliminates covariance estimation noise using Random Matrix Theory (RMT) and allocates capital via Hierarchical Risk Parity (HRP).

| Dimension                | Specification                                                   |
| :----------------------- | :-------------------------------------------------------------- |
| **Optimization Method**  | Hierarchical Risk Parity (HRP) + Single Linkage Clustering      |
| **Noise Filtering**      | Random Matrix Theory (RMT) Marchenko-Pastur Eigenvalue Clipping |
| **Data Provider**        | Tiingo API Automated Ingestion Pipeline                         |
| **Benchmark Comparison** | Equal-Weight (1/N) and Traditional Markowitz Mean-Variance      |
| **Primary Stack**        | Python, SciPy, Scikit-Learn, Seaborn, Matplotlib, Tiingo API    |

---

## Mathematical Foundation

Noise eigenvalues are separated from signal eigenvalues using the Marchenko-Pastur distribution upper bound:

$$\lambda_{max} = \sigma^2 \left(1 + \sqrt{\frac{N}{T}}\right)^2$$

Eigenvalues below $\lambda_{max}$ are replaced with their average, constructing a clean covariance matrix before hierarchical clustering.
