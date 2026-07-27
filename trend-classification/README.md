# Supervised Trend Classification & Machine Learning Signals

[ English ] | [ [Versión en Español](docs/README_ES.md) ]

---

## Executive Summary

> [!NOTE]
> **Core Objective:** Develop a Machine Learning directional trend classification pipeline using Triple Barrier Method labeling and ensemble models evaluated via Combinatorial Purged Cross-Validation.

| Dimension               | Specification                                                   |
| :---------------------- | :-------------------------------------------------------------- |
| **Labeling Technique**  | Triple Barrier Method (Profit Take, Stop Loss, Time Expiration) |
| **Models Evaluated**    | XGBoost, LightGBM, Random Forest, Logistic Regression           |
| **Validation Protocol** | Combinatorial Purged Cross-Validation (CPCV)                    |
| **Metrics Tracked**     | Out-of-Sample ROC-AUC, Precision, Recall, F1-Score, Log-Loss    |
| **Primary Stack**       | Python, Scikit-Learn, XGBoost, LightGBM, Parquet                |
