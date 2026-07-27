import os
import sys

import pandas as pd

ruta_actual = os.path.dirname(os.path.abspath(__file__))
ruta_raiz = os.path.abspath(os.path.join(ruta_actual, ".."))
if ruta_raiz not in sys.path:
    sys.path.insert(0, ruta_raiz)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from Capa_5.validation_protocols import (
    build_fixed_oos_split,
    build_purged_embargo_folds,
    summarize_fixed_oos_split,
    summarize_folds,
)


def ejecutar_validacion_purga_embargo():
    ruta_lago = os.path.join(ruta_raiz, "XAUUSD_M15_Training.parquet")
    ruta_reporte = os.path.join(ruta_actual, "auditoria_capa5_purged_embargo.csv")
    ruta_reporte_oos = os.path.join(ruta_actual, "auditoria_capa5_fixed_oos_202405.csv")
    ruta_is_purged = os.path.join(ruta_actual, "XAUUSD_M15_IS_PURGED.parquet")
    ruta_oos = os.path.join(ruta_actual, "XAUUSD_M15_OOS_202405.parquet")

    print("=========================================================================")
    print("CAPA 5: PROTOCOLO OOS CON PURGA Y EMBARGO")
    print("=========================================================================")

    if not os.path.exists(ruta_lago):
        print(f"ERROR: Lago de Datos no encontrado en: {ruta_lago}")
        return

    df = pd.read_parquet(ruta_lago)
    folds = build_purged_embargo_folds(df.index, n_splits=5, label_horizon=120, embargo=120)
    summary = summarize_folds(folds, df.index)
    summary.to_csv(ruta_reporte, index=False)
    fixed_oos = build_fixed_oos_split(df.index, "2024-05-01", label_horizon=120, embargo=120)
    fixed_summary = summarize_fixed_oos_split(fixed_oos, df.index)
    fixed_summary.to_csv(ruta_reporte_oos, index=False)
    df.iloc[fixed_oos.train_indices].to_parquet(ruta_is_purged, engine="pyarrow", compression="snappy")
    df.iloc[fixed_oos.test_indices].to_parquet(ruta_oos, engine="pyarrow", compression="snappy")

    print("Folds cronologicos purgados/embargados:")
    print(summary.to_string(index=False))
    print("\nSplit fijo IS/OOS desde 2024-05-01:")
    print(fixed_summary.to_string(index=False))
    print(f"Reporte: {ruta_reporte}")
    print(f"Reporte OOS fijo: {ruta_reporte_oos}")
    print(f"Parquet IS purgado: {ruta_is_purged}")
    print(f"Parquet OOS fijo: {ruta_oos}")
    print("=========================================================================")


if __name__ == "__main__":
    ejecutar_validacion_purga_embargo()
