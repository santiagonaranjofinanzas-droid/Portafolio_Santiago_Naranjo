import os
import sys
import pandas as pd

#Configurar codificación de salida
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

#Resolver rutas para importar del proyecto principal
ruta_actual = os.path.dirname(os.path.abspath(__file__))
ruta_raiz = os.path.abspath(os.path.join(ruta_actual, "..", ".."))

if ruta_raiz not in sys.path:
    sys.path.insert(0, ruta_raiz)

from Capa_5.validation_protocols import (
    build_purged_embargo_folds,
    build_fixed_oos_split,
    summarize_folds,
    summarize_fixed_oos_split,
)

def ejecutar_validacion_activo(
    ruta_lago: str,
    asset_name: str,
    oos_start_date: str = "2024-05-01",
    label_horizon: int = 120,
    embargo: int = 120,
    dir_salida: str = None
) -> dict:
    """
    Capa 5: Ejecuta el protocolo de validación cruzada con purga y embargo para el activo.
    Genera conjuntos de entrenamiento IS y evaluación OOS limpios de solapamiento.
    """
    print("=========================================================================")
    print(f" CAPA 5: VALIDACIÓN OOS CON PURGA Y EMBARGO - {asset_name.upper()}")
    print("=========================================================================")
    
    if not os.path.exists(ruta_lago):
        raise FileNotFoundError(f"Lago de datos no encontrado: {ruta_lago}")
        
    df = pd.read_parquet(ruta_lago)
    print(f"• Cargadas {len(df)} velas desde el lago de datos.")
    
    # 1. Construir Folds Cronológicos
    print(f"• Construyendo 5 Folds con horizonte de etiquetas={label_horizon} y embargo={embargo}...")
    folds = build_purged_embargo_folds(df.index, n_splits=5, label_horizon=label_horizon, embargo=embargo)
    summary_folds = summarize_folds(folds, df.index)
    
    # 2. Construir Split Fijo
    print(f"• Construyendo Split IS/OOS Fijo con fecha corte {oos_start_date}...")
    # Asegurar que la fecha de corte esté en el rango del índice
    if pd.Timestamp(oos_start_date) < df.index.min() or pd.Timestamp(oos_start_date) > df.index.max():
        raise ValueError("La fecha OOS está fuera del rango del dataset.")
        
    fixed_oos = build_fixed_oos_split(df.index, oos_start_date, label_horizon=label_horizon, embargo=embargo)
    summary_fixed = summarize_fixed_oos_split(fixed_oos, df.index)
    
    # Resolver rutas de salida
    if not dir_salida:
        dir_salida = os.path.abspath(os.path.join(ruta_actual, "..", "resultados"))
    os.makedirs(dir_salida, exist_ok=True)
    
    ruta_reporte_folds = os.path.join(dir_salida, f"{asset_name.upper()}_capa5_purged_embargo_folds.csv")
    ruta_reporte_fixed = os.path.join(dir_salida, f"{asset_name.upper()}_capa5_fixed_oos_split.csv")
    ruta_is_purged = os.path.join(dir_salida, f"{asset_name.upper()}_M15_IS_PURGED.parquet")
    ruta_oos = os.path.join(dir_salida, f"{asset_name.upper()}_M15_OOS.parquet")
    
    # Guardar reportes y datos
    summary_folds.to_csv(ruta_reporte_folds, index=False)
    summary_fixed.to_csv(ruta_reporte_fixed, index=False)
    
    df.iloc[fixed_oos.train_indices].to_parquet(ruta_is_purged, engine="pyarrow", compression="snappy")
    df.iloc[fixed_oos.test_indices].to_parquet(ruta_oos, engine="pyarrow", compression="snappy")
    
    print("\n Resumen de Folds:")
    print(summary_folds.to_string(index=False))
    print("\n Split Fijo:")
    print(summary_fixed.to_string(index=False))
    
    print(f"\n CAPA 5 COMPLETADA")
    print(f" • Reporte Folds:     {ruta_reporte_folds}")
    f" • Reporte Fijo:      {ruta_reporte_fixed}"
    print(f" • Parquet IS Purgado:{ruta_is_purged}")
    print(f" • Parquet OOS:       {ruta_oos}")
    print("=========================================================================\n")
    
    return {
        "is_purged_path": ruta_is_purged,
        "oos_path": ruta_oos,
        "folds_summary": summary_folds,
        "fixed_summary": summary_fixed
    }

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        ejecutar_validacion_activo(sys.argv[1], sys.argv[2])
    else:
        print("Uso: python validacion_cruzada.py <ruta_lago> <nombre_activo> [fecha_oos_start]")
