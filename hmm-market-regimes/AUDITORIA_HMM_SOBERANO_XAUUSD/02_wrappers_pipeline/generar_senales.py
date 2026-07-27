import os
import sys
import pandas as pd

#Configurar codificación de salida
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

#Resolver rutas para importar de las capas anteriores
ruta_actual = os.path.dirname(os.path.abspath(__file__))
ruta_raiz = os.path.abspath(os.path.join(ruta_actual, "..", ".."))

if ruta_raiz not in sys.path:
    sys.path.insert(0, ruta_raiz)

from Capa_2.sovereign_signal import run_sovereign_signal_engine

def generar_senales_activo(ruta_lago: str, asset_name: str, ruta_params: str, point: float = 0.01, ruta_salida: str = None) -> str:
    """
    Capa 2: Inferencia de señales del modelo HMM 30001 para el activo indicado.
    Lee los parámetros calibrados y genera buffers de señales (HMM_Prob_Bull, ML_Master_Strength, etc.)
    """
    print("=========================================================================")
    print(f" CAPA 2: GENERACIÓN DE SEÑALES - {asset_name.upper()}")
    print("=========================================================================")
    
    if not os.path.exists(ruta_lago):
        raise FileNotFoundError(f"Lago de datos no encontrado: {ruta_lago}")
    if not os.path.exists(ruta_params):
        raise FileNotFoundError(f"Parámetros HMM no encontrados: {ruta_params}")
        
    df = pd.read_parquet(ruta_lago)
    
    print(f"• Cargados {len(df)} registros de precios.")
    print(f"• Usando parámetros desde: {ruta_params}")
    print(f"• Medida del punto (point size): {point}")
    
    # Ejecución del motor secuencial
    signals = run_sovereign_signal_engine(df, params_csv=ruta_params, point=point)
    
    if not ruta_salida:
        dir_resultados = os.path.abspath(os.path.join(ruta_actual, "..", "resultados"))
        os.makedirs(dir_resultados, exist_ok=True)
        ruta_salida = os.path.join(dir_resultados, f"{asset_name.upper()}_signals.csv")
        
    signals.to_csv(ruta_salida, sep=",")
    
    print(f" CAPA 2 COMPLETADA")
    print(f" • Destino de señales: {ruta_salida}")
    print(f" • P(Bull) final: {signals['HMM_Prob_Bull'].iloc[-1]:.4f}")
    print(f" • Régimen final: {int(signals['Regime_Buffer_18'].iloc[-1])}")
    print(f" • Volatilidad proyectada final: {signals['Vol_Projected_Sigma'].iloc[-1] * 100:.4f}%")
    print(f" • Fuerza (ML Strength) final: {signals['ML_Master_Strength'].iloc[-1] * 100:.2f}%")
    print("=========================================================================\n")
    return ruta_salida

if __name__ == "__main__":
    if len(sys.argv) >= 5:
        ruta_lago = sys.argv[1]
        asset_name = sys.argv[2]
        ruta_params = sys.argv[3]
        point = float(sys.argv[4])
        generar_senales_activo(ruta_lago, asset_name, ruta_params, point)
    else:
        print("Uso: python generar_senales.py <ruta_lago> <nombre_activo> <ruta_params> <point>")
