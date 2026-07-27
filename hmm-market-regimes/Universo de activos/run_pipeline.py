import os
import sys
import argparse
import json
from pathlib import Path

#Configurar codificación de salida
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

#Resolver rutas para importar capas locales
ruta_actual = os.path.dirname(os.path.abspath(__file__))
if ruta_actual not in sys.path:
    sys.path.insert(0, ruta_actual)

from Capa_0_Datos.procesar_datos import procesar_datos_activo
from Capa_2_Signal.generar_senales import generar_senales_activo
from Capa_3_Calibration.calibrar_hmm import calibrar_hmm_activo
from Capa_4_Execution.backtest_activo import ejecutar_backtest_activo
from Capa_5_Validation.validacion_cruzada import ejecutar_validacion_activo
from Capa_6_WalkForward.walk_forward_activo import ejecutar_walk_forward_activo

def main():
    parser = argparse.ArgumentParser(description="Orquestador Maestro HMM Sovereign - Multiactivo")
    parser.add_argument("--asset", required=True, type=str, help="Nombre del activo (ej. NAS100, SILVER, XAUUSD)")
    parser.add_argument("--data", required=True, type=str, help="Ruta al archivo de datos de origen (CSV o Parquet)")
    parser.add_argument("--point", type=float, default=0.01, help="Medida del punto del activo (point size, default=0.01)")
    parser.add_argument("--tick-size", type=float, default=0.01, help="Tamaño mínimo de tick del activo (default=0.01)")
    parser.add_argument("--tick-value", type=float, default=1.0, help="Valor monetario de un tick del activo (default=1.0)")
    parser.add_argument("--spread", type=float, default=0.0, help="Spread simulado en unidades de precio, no en points MT5 (default=0.0)")
    parser.add_argument("--slippage", type=float, default=0.0, help="Slippage simulado en puntos de precio (default=0.0)")
    parser.add_argument("--steps", type=str, default="all", help="Pasos de capas a ejecutar separados por coma (ej. 0,3,2,4,5,6 o 'all')")
    parser.add_argument("--max-candidates", type=int, default=18, help="Máximo de candidatos para Capa 6 (grilla rápida default=18, full=None)")
    parser.add_argument("--commission", type=float, default=0.0, help="Comisión por lote per side (default=0.0)")
    parser.add_argument("--min-lot", type=float, default=0.01, help="Mínimo lote permitido (default=0.01)")
    parser.add_argument("--lot-step", type=float, default=0.01, help="Paso del lote permitido (default=0.01)")
    parser.add_argument("--intrabar-mode", type=str, default="pessimistic", help="Modo intrabar para parciales/TP/SL ('pessimistic' o 'normal')")
    
    args = parser.parse_args()
    
    asset = args.asset.upper()
    data_path = args.data
    
    # Determinar qué pasos ejecutar
    if args.steps.lower() == "all":
        steps_to_run = [0, 3, 2, 4, 5, 6]
    else:
        steps_to_run = [int(s.strip()) for s in args.steps.split(",")]
        
    print("=========================================================================")
    print(f" INICIANDO PIPELINE QUANT SOVEREIGN HMM - ACTIVO: {asset}")
    print("=========================================================================")
    print(f" • Datos origen: {data_path}")
    print(f" • Point size:   {args.point}  Tick size: {args.tick_size}  Tick value: {args.tick_value}")
    print(f" • Pasos a ejecutar: {steps_to_run}")
    print("=========================================================================\n")
    
    dir_datos = os.path.join(ruta_actual, "datos")
    dir_resultados = os.path.join(ruta_actual, "resultados", asset)
    os.makedirs(dir_datos, exist_ok=True)
    os.makedirs(dir_resultados, exist_ok=True)
    
    # Rutas por defecto del ciclo de vida del activo
    ruta_lago = os.path.join(dir_datos, f"{asset}_M15_Training.parquet")
    ruta_params = os.path.join(dir_resultados, f"HMM_Params_15M_{asset}.csv")
    ruta_signals = os.path.join(dir_resultados, f"{asset}_signals.csv")
    
    # Paso 0: Capa 0 - Procesamiento de Datos
    if 0 in steps_to_run:
        procesar_datos_activo(data_path, asset, ruta_lago)
    else:
        if not os.path.exists(ruta_lago):
            print(f" Advertencia: El lago de datos {ruta_lago} no existe pero el Paso 0 se saltó. Intentando usar {data_path} directamente...")
            ruta_lago = data_path

    # Paso 5: Capa 5 - Validación Cruzada Purgada y Embargada (Split IS/OOS)
    # Se ejecuta ANTES de Capa 3 para evitar Data Snooping
    if 5 in steps_to_run:
        ejecutar_validacion_activo(ruta_lago, asset, oos_start_date="2024-05-01", dir_salida=dir_resultados)
        
    ruta_is_purged = os.path.join(dir_resultados, f"{asset}_M15_IS_PURGED.parquet")
    ruta_oos = os.path.join(dir_resultados, f"{asset}_M15_OOS.parquet")
            
    # Paso 3: Capa 3 - Calibración HMM
    if 3 in steps_to_run:
        if os.path.exists(ruta_is_purged):
            print(" Usando dataset IS_PURGED para calibración (Anti-Data Leakage).")
            calibrar_hmm_activo(ruta_is_purged, asset, ruta_params)
        else:
            print(" Advertencia: No se encontró IS_PURGED. Calibrando sobre lago completo (¡Riesgo de Data Snooping!).")
            calibrar_hmm_activo(ruta_lago, asset, ruta_params)
        
    # Paso 2: Capa 2 - Inferencia de Señales (IS y OOS separados)
    ruta_signals_is = os.path.join(dir_resultados, f"{asset}_signals_IS.csv")
    ruta_signals_oos = os.path.join(dir_resultados, f"{asset}_signals_OOS.csv")
    if 2 in steps_to_run:
        if not os.path.exists(ruta_params):
            raise FileNotFoundError(f" Error: Se requieren parámetros calibrados ({ruta_params}) para generar señales. Ejecute la Capa 3.")
        
        if os.path.exists(ruta_is_purged):
            generar_senales_activo(ruta_is_purged, f"{asset}_IS", ruta_params, args.point, ruta_signals_is)
        else:
            generar_senales_activo(ruta_lago, asset, ruta_params, args.point, ruta_signals_is) # Fallback
            
        if os.path.exists(ruta_oos):
            generar_senales_activo(ruta_oos, f"{asset}_OOS", ruta_params, args.point, ruta_signals_oos)
        
    # Calcular dsr_trials dinámicamente desde parameter_space.json
    dsr_trials = 81
    ruta_raiz = os.path.abspath(os.path.join(ruta_actual, ".."))
    ruta_space = os.path.join(ruta_raiz, "Capa_6", "parameter_space.json")
    if os.path.exists(ruta_space):
        try:
            with open(ruta_space, "r", encoding="utf-8") as handle:
                space = json.load(handle)
            keys = ["threshold", "min_strength", "vol_multiplier", "reward_risk", "kalman_gate"]
            num_combos = 1
            for k in keys:
                if k in space and isinstance(space[k], list):
                    num_combos *= len(space[k])
            dsr_trials = num_combos
            print(f" DSR Trials detectado desde parameter_space.json: {dsr_trials}")
        except Exception as e:
            print(f" Error calculando dsr_trials, usando default 81: {e}")
            dsr_trials = 81
    else:
        print(f" No se encontró parameter_space.json en {ruta_space}, usando default 81.")

    # Paso 4: Capa 4 - Ejecución de Backtest y Reporte Financiero (IS y OOS)
    if 4 in steps_to_run:
        if os.path.exists(ruta_signals_is):
            ejecutar_backtest_activo(
                ruta_signals=ruta_signals_is,
                asset_name=f"{asset}_IS",
                point=args.point,
                tick_size=args.tick_size,
                tick_value=args.tick_value,
                spread_price=args.spread,
                slippage_price=args.slippage,
                commission_per_lot=args.commission,
                min_lot=args.min_lot,
                lot_step=args.lot_step,
                intrabar_mode=args.intrabar_mode,
                dsr_trials=dsr_trials,
                ruta_salida_reporte=os.path.join(dir_resultados, f"REPORTE_IS_{asset}.md")
            )
        if os.path.exists(ruta_signals_oos):
            ejecutar_backtest_activo(
                ruta_signals=ruta_signals_oos,
                asset_name=f"{asset}_OOS",
                point=args.point,
                tick_size=args.tick_size,
                tick_value=args.tick_value,
                spread_price=args.spread,
                slippage_price=args.slippage,
                commission_per_lot=args.commission,
                min_lot=args.min_lot,
                lot_step=args.lot_step,
                intrabar_mode=args.intrabar_mode,
                dsr_trials=dsr_trials,
                ruta_salida_reporte=os.path.join(dir_resultados, f"REPORTE_OOS_{asset}.md")
            )
        
    # Paso 6: Capa 6 - Walk-Forward y Estabilidad de Grid Search
    if 6 in steps_to_run:
        # Usamos el IS_PURGED generado en Capa 5 como entrada para el Walk Forward
        if not os.path.exists(ruta_is_purged):
            print(f" Advertencia: No se encontró {ruta_is_purged}. Usando lago completo para Walk-Forward.")
            ruta_wf_input = ruta_lago
        else:
            ruta_wf_input = ruta_is_purged
            
        ejecutar_walk_forward_activo(
            ruta_lago=ruta_wf_input,
            asset_name=asset,
            point=args.point,
            tick_size=args.tick_size,
            tick_value=args.tick_value,
            spread_price=args.spread,
            slippage_price=args.slippage,
            max_candidates=args.max_candidates,
            commission_per_lot=args.commission,
            min_lot=args.min_lot,
            lot_step=args.lot_step,
            intrabar_mode=args.intrabar_mode,
            dsr_trials=dsr_trials,
            dir_salida=os.path.join(dir_resultados, f"{asset}_nested_walk_forward")
        )

        # EJECUTAR OPTIMIZACIÓN EN EL HOLDOUT COMPLETO (PRUEBA CLAVE DEL AUDITOR)
        if os.path.exists(ruta_is_purged) and os.path.exists(ruta_oos):
            print("\n EJECUTANDO OPTIMIZADOR EN EL HOLDOUT COMPLETO...")
            from Capa_6.optimizer import run_optimization
            asset_cfg = {
                "point": args.point,
                "tick_size": args.tick_size,
                "tick_value": args.tick_value,
                "spread_price": args.spread,
                "slippage_price": args.slippage,
                "commission_per_lot": args.commission,
                "min_lot": args.min_lot,
                "lot_step": args.lot_step,
                "intrabar_mode": args.intrabar_mode,
            }
            run_optimization(
                is_path=Path(ruta_is_purged),
                oos_path=Path(ruta_oos),
                params_path=Path(ruta_params),
                space_path=Path(ruta_space),
                out_dir=Path(dir_resultados),
                max_candidates=None, # Usar todos los candidatos
                dsr_trials=dsr_trials,
                asset_cfg=asset_cfg
            )
            print(" OPTIMIZADOR TERMINADO. ARCHIVOS OOS EXPORTADOS CORRECTAMENTE.")
        
    print("=========================================================================")
    print(f" PIPELINE TERMINADO PARA EL ACTIVO {asset}")
    print("=========================================================================")

if __name__ == "__main__":
    main()
