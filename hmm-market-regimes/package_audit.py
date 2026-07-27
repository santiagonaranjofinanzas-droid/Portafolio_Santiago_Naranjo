import os
import shutil
import json
import zipfile
from pathlib import Path

#Paths
ROOT = Path(r"c:\Users\YOUR_USERNAME\Desktop\Trading\1_#####HMM#####")
ASSET = "XAUUSD"
ZIP_NAME = "AUDITORIA_HMM_SOBERANO_XAUUSD.zip"
AUDIT_DIR = ROOT / "AUDITORIA_HMM_SOBERANO_XAUUSD"

#Create struct
if AUDIT_DIR.exists():
    shutil.rmtree(AUDIT_DIR)

dirs = [
    "01_codigo_core", "02_wrappers_pipeline", "03_configuracion", 
    "04_datos", "05_parametros_hmm", "06_senales", 
    "07_resultados_backtest", "08_walk_forward", "09_reportes"
]

for d in dirs:
    (AUDIT_DIR / d).mkdir(parents=True, exist_ok=True)

def copy_file(src, dst_dir, dst_name=None):
    src_path = Path(src)
    if src_path.exists():
        dst_path = AUDIT_DIR / dst_dir / (dst_name if dst_name else src_path.name)
        shutil.copy2(src_path, dst_path)
    else:
        print(f"File not found: {src_path}")

#01
copy_file(ROOT / "Capa_1/sovereign_core.py", "01_codigo_core")
copy_file(ROOT / "Capa_2/sovereign_signal.py", "01_codigo_core")
copy_file(ROOT / "Capa_3/sovereign_calibration.py", "01_codigo_core")
copy_file(ROOT / "Capa_4/sovereign_execution.py", "01_codigo_core")
copy_file(ROOT / "Capa_4/backtest_metrics.py", "01_codigo_core")
copy_file(ROOT / "Capa_5/validation_protocols.py", "01_codigo_core")
copy_file(ROOT / "Capa_6/optimizer.py", "01_codigo_core")

#02
copy_file(ROOT / "Universo de activos/Capa_0_Datos/procesar_datos.py", "02_wrappers_pipeline")
copy_file(ROOT / "Universo de activos/Capa_3_Calibration/calibrar_hmm.py", "02_wrappers_pipeline")
copy_file(ROOT / "Universo de activos/Capa_2_Signal/generar_senales.py", "02_wrappers_pipeline")
copy_file(ROOT / "Universo de activos/Capa_4_Execution/backtest_activo.py", "02_wrappers_pipeline")
copy_file(ROOT / "Universo de activos/Capa_5_Validation/validacion_cruzada.py", "02_wrappers_pipeline")
copy_file(ROOT / "Universo de activos/Capa_6_WalkForward/walk_forward_activo.py", "02_wrappers_pipeline")
copy_file(ROOT / "Universo de activos/resultados/ablation_and_segmentation_analysis.py", "02_wrappers_pipeline")
copy_file(ROOT / "run_stress_tests.py", "02_wrappers_pipeline")
copy_file(ROOT / "package_audit.py", "02_wrappers_pipeline")

#03
copy_file(ROOT / "Capa_6/parameter_space.json", "03_configuracion")
copy_file(ROOT / "requirements.txt", "03_configuracion")

#04
res = ROOT / f"Universo de activos/resultados/{ASSET}"
datos = ROOT / "Universo de activos/datos"
copy_file(datos / f"{ASSET}_M15_Training.parquet", "04_datos")
copy_file(res / f"{ASSET}_M15_IS_PURGED.parquet", "04_datos")
copy_file(res / f"{ASSET}_M15_OOS.parquet", "04_datos")

#05
copy_file(res / f"HMM_Params_15M_{ASSET}.csv", "05_parametros_hmm", f"HMM_Params_{ASSET}_IS_ONLY.csv")
wf_dir = res / f"{ASSET}_nested_walk_forward"
for i in range(4):
    copy_file(wf_dir / f"fold_{i}/HMM_Params_fold.csv", "05_parametros_hmm", f"HMM_Params_fold_{i}.csv")

#06
copy_file(res / f"{ASSET}_signals_IS.csv", "06_senales")
copy_file(res / f"{ASSET}_signals_OOS.csv", "06_senales")

#07
copy_file(res / "trades__IS.csv", "07_resultados_backtest", "trades_IS.csv")
copy_file(res / "trades_OOS.csv", "07_resultados_backtest")
copy_file(res / "cashflows__IS.csv", "07_resultados_backtest", "cashflows_IS.csv")
copy_file(res / "cashflows_OOS.csv", "07_resultados_backtest")
copy_file(res / "equity__IS.csv", "07_resultados_backtest", "equity_IS.csv")
copy_file(res / "equity_OOS.csv", "07_resultados_backtest")
copy_file(res / "metrics__IS.csv", "07_resultados_backtest", "metrics_IS.csv")
copy_file(res / "metrics_OOS.csv", "07_resultados_backtest")
copy_file(res / "best_oos_holdout_metrics.csv", "07_resultados_backtest")
copy_file(res / "best_oos_trades.csv", "07_resultados_backtest")
copy_file(res / "best_oos_cashflows.csv", "07_resultados_backtest")
copy_file(res / "best_oos_equity.csv", "07_resultados_backtest")

#08
copy_file(wf_dir / "folds.csv", "08_walk_forward")
copy_file(wf_dir / "nested_all_rankings.csv", "08_walk_forward")
copy_file(wf_dir / "nested_stability_ranking.csv", "08_walk_forward")

#09
copy_file(res / f"REPORTE_IS_{ASSET}.md", "09_reportes", f"REPORTE_ROBUSTEZ_{ASSET}.md")
copy_file(res / "alpha_decay_oos_quarterly.csv", "09_reportes")
copy_file(ROOT / "stress_spread_x1.csv", "09_reportes")
copy_file(ROOT / "stress_spread_x2.csv", "09_reportes")
copy_file(ROOT / "stress_spread_x3.csv", "09_reportes")
copy_file(ROOT / "stress_slippage.csv", "09_reportes")
copy_file(ROOT / "auditoria_cambios_realizados.md", "09_reportes")
copy_file(res / "REPORTE_ANALISIS_MODELO_XAUUSD.md", "09_reportes")

#Copiar nuevos CSVs de segmentación y ablación
new_csvs = [
    "baseline_metrics.csv",
    "direction_segmentation.csv",
    "session_segmentation.csv",
    "volatility_segmentation.csv",
    "direction_session_matrix.csv",
    "ablation_results.csv",
    "dynamic_threshold_results.csv",
    "cost_sensitivity_results.csv",
    "post_2024_decay.csv",
    "exit_reason_analysis.csv",
    "component_contribution_summary.csv",
    "trades_ablation_base.csv",
    "trades_best_segment.csv",
    "equity_best_segment.csv"
]
for csv_f in new_csvs:
    copy_file(res / csv_f, "07_resultados_backtest")

#Create JSON config
cfg = {
  "symbol": "XAUUSD",
  "point": 0.01,
  "tick_size": 0.01,
  "tick_value": 1.0,
  "spread_price": 0.15,
  "commission_per_lot": 3.0,
  "slippage_price": 0.05,
  "min_lot": 0.01,
  "lot_step": 0.01,
  "max_lot": 10.0,
  "timezone": "America/New_York",
  "source_timezone": "UTC",
  "session_timezone": "America/New_York",
  "oos_start_date": "2024-05-01"
}
with open(AUDIT_DIR / "03_configuracion/asset_config_xauusd.json", "w") as f:
    json.dump(cfg, f, indent=2)

print("Done setting up structure.")

#Make zip
shutil.make_archive(str(ROOT / "AUDITORIA_HMM_SOBERANO_XAUUSD"), 'zip', str(AUDIT_DIR))
print("Zip created.")
