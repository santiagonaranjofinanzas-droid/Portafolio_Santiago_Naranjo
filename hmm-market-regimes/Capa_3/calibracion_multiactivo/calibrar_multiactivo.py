import os
import sys
import pandas as pd
import numpy as np

#Configurar codificación de salida para consola
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

#Resolver rutas para poder importar de las capas anteriores
ruta_actual = os.path.dirname(os.path.abspath(__file__))
ruta_capa3 = os.path.abspath(os.path.join(ruta_actual, ".."))
ruta_raiz = os.path.abspath(os.path.join(ruta_capa3, ".."))

if ruta_raiz not in sys.path:
    sys.path.insert(0, ruta_raiz)
if ruta_capa3 not in sys.path:
    sys.path.insert(0, ruta_capa3)

from Capa_3.sovereign_calibration import CSystemCalibrator

def cargar_datos_precio(ruta_archivo: str) -> np.ndarray:
    """
    Carga precios de cierre de archivos CSV (incluyendo exports MT5) o Parquet,
    limpia duplicados y los ordena cronológicamente.
    """
    if not os.path.exists(ruta_archivo):
        raise FileNotFoundError(f"El archivo de datos no existe: {ruta_archivo}")
        
    _, ext = os.path.splitext(ruta_archivo.lower())
    print(f" Cargando datos desde: {ruta_archivo} (formato {ext})")
    
    if ext == '.parquet':
        df = pd.read_parquet(ruta_archivo)
    elif ext == '.csv':
        try:
            # Intentar detectar separador automáticamente (MT5 suele usar tabuladores o comas)
            df = pd.read_csv(ruta_archivo, sep=None, engine='python')
        except Exception:
            df = pd.read_csv(ruta_archivo, sep=',')
    else:
        raise ValueError(f"Formato no soportado: {ext}. Use .parquet o .csv")
        
    # Normalizar nombres de columnas a minúsculas, quitando espacios y caracteres como < >
    df.columns = [c.lower().strip().replace('<', '').replace('>', '') for c in df.columns]
    
    # Buscar columna de precio de cierre
    col_close = None
    for col in ['close', 'close_raw', 'ultimo', 'last', 'c']:
        if col in df.columns:
            col_close = col
            break
            
    if col_close is None:
        raise KeyError(f"No se encontró la columna de precio de cierre ('close') en el archivo. Columnas disponibles: {list(df.columns)}")
    
    # Intentar ordenar por fecha si existe columna temporal
    col_time = None
    for col in ['timestamp', 'time', 'date', 'datetime', 'fecha', 't']:
        if col in df.columns:
            col_time = col
            break
            
    if col_time:
        df[col_time] = pd.to_datetime(df[col_time])
        df = df.sort_values(by=col_time)
        print(f" Datos ordenados por tiempo usando la columna '{col_time}'.")
    else:
        print(" Advertencia: No se encontró columna de fecha/hora. Asumiendo que los datos ya están en orden cronológico.")
        
    precios = df[col_close].dropna().values
    print(f" Total de velas de precio cargadas: {len(precios)}")
    return precios

def calibrar_activo(ruta_datos: str, asset_name: str, ruta_salida: str = None):
    """
    Ejecuta el pipeline completo de calibración HMM (MoM + MLE) para un activo específico.
    """
    try:
        close_raw = cargar_datos_precio(ruta_datos)
    except Exception as e:
        print(f" Error al cargar datos: {str(e)}")
        return
        
    rates_total = len(close_raw)
    if rates_total < 200:
        print(f" Error: Datos insuficientes ({rates_total} velas). Se requieren al menos 200 velas.")
        return
        
    print(f"\n=========================================================================")
    # Identificar el activo y proceder con calibración
    print(f" CALIBRACIÓN HMM SISTEMA 30001 - ACTIVO: {asset_name.upper()}")
    print(f"=========================================================================")
    
    # Reconstrucción de los vectores de retornos exactos del OnCalculate de Sovereign
    b_returns = np.zeros(rates_total)
    for i in range(2, rates_total):
        b_returns[i] = np.log(close_raw[i-1] / close_raw[i-2])
        
    # Inicialización de estadísticas rodantes idénticas a MQL5 (Capa 2)
    alpha_20 = 2.0 / (20 + 1.0)
    b_mu_rets = np.zeros(rates_total)
    b_mu_rets[0] = b_returns[0]
    for i in range(1, rates_total):
        b_mu_rets[i] = b_returns[i] * alpha_20 + b_mu_rets[i-1] * (1.0 - alpha_20)
        
    b_sig_rets = np.zeros(rates_total)
    b_kurtosis = np.zeros(rates_total)
    for i in range(rates_total):
        if i >= 59:
            b_sig_rets[i] = np.std(b_returns[i-59:i+1], ddof=1)
        if i >= 119:
            window = b_returns[i-119:i+1]
            mean_w = np.mean(window)
            m2 = np.mean((window - mean_w)**2)
            m4 = np.mean((window - mean_w)**4)
            b_kurtosis[i] = (m4 / (m2 * m2)) - 3.0 if m2 > 1e-20 else 0.0

    print("• Lanzando estimación por momentos para el componente de Salto...")
    nu_opt, lambda_opt, lr_sigma = CSystemCalibrator.estimate_moments_distribution(b_returns, jump_sigma_k=3.0)
    
    print("• Ejecutando optimización por máxima verosimilitud de la matriz HMM...")
    p_bull_opt, p_bear_opt = CSystemCalibrator.optimize_hmm_matrix(
        b_returns, b_mu_rets, b_sig_rets, b_kurtosis, nu_opt, lambda_opt
    )
    
    # Constantes estructurales del contrato (pueden ser ajustadas o mantenidas en valores estándar)
    WConf = 0.5; WVol = 0.5; WSlope = 0.5; WAccel = 0.0; WInter = 0.0
    MuConf = 0.4820; StdConf = 0.2215
    MuVol = 1.0; StdVol = 0.5
    MuSlope = 1.0; StdSlope = 2.0
    MuAccel = 0.0; StdAccel = 1.0
    ExtSlopeT = 0.0273

    df_csv = pd.DataFrame({
        "InpPBull": [p_bull_opt],
        "InpPBear": [p_bear_opt],
        "InpSlopeT": [ExtSlopeT],
        "InpLambdaJ": [lambda_opt],
        "InpNu": [nu_opt],
        "WConf": [WConf],
        "WVol": [WVol],
        "WSlope": [WSlope],
        "WAccel": [WAccel],
        "WInter": [WInter],
        "MuConf": [MuConf],
        "MuVol": [MuVol],
        "MuSlope": [MuSlope],
        "MuAccel": [MuAccel],
        "StdConf": [StdConf],
        "StdVol": [StdVol],
        "StdSlope": [StdSlope],
        "StdAccel": [StdAccel]
    })

    if not ruta_salida:
        ruta_salida = os.path.join(ruta_actual, f"HMM_Params_15M_{asset_name.upper()}.csv")
        
    df_csv.to_csv(ruta_salida, index=False, sep=",")
    
    print("\n=========================================================================")
    print(f" CALIBRACIÓN LOGRADA: ARCHIVO HMM_PARAMS PARA {asset_name.upper()} GENERADO")
    print("=========================================================================")
    print(f" • Destino CSV:      {ruta_salida}")
    print(f" • Parámetros HMM:   P(Bull) = {p_bull_opt:.4f}  P(Bear) = {p_bear_opt:.4f}")
    print(f" • Proceso de Salto: Grados Libertad ν = {nu_opt:.4f}  Tasa Saltos λ = {lambda_opt*100:.2f}%")
    print(f" • Sigma Residual:   {lr_sigma:.6f}")
    print("=========================================================================\n")

def main():
    # Permitir ejecución por línea de comandos pasando la ruta del archivo de datos y el nombre del activo
    # Sintaxis: python calibrar_multiactivo.py [ruta_archivo] [nombre_activo]
    if len(sys.argv) >= 3:
        ruta_datos = sys.argv[1]
        asset_name = sys.argv[2]
        calibrar_activo(ruta_datos, asset_name)
    else:
        # Modo por defecto: buscar archivos en la carpeta 'datos' si existen
        dir_datos = os.path.join(ruta_actual, "datos")
        if os.path.exists(dir_datos):
            archivos = [os.path.join(dir_datos, f) for f in os.listdir(dir_datos) 
                        if f.lower().endswith(('.parquet', '.csv'))]
            if archivos:
                print(f" Se encontraron {len(archivos)} archivos de datos en {dir_datos}. Procesando...")
                for archivo in archivos:
                    nombre_archivo = os.path.basename(archivo)
                    asset_name = nombre_archivo.split('_')[0].split('.')[0]
                    calibrar_activo(archivo, asset_name)
            else:
                print(f"ℹ No se encontraron archivos de datos (.csv / .parquet) en {dir_datos}.")
                mostrar_ayuda()
        else:
            os.makedirs(dir_datos, exist_ok=True)
            print(f"ℹ Se creó la carpeta de datos en: {dir_datos}")
            print("Coloque sus archivos de precios (como 'NAS100_M15.csv' o 'XAGUSD_M15.parquet') allí.")
            mostrar_ayuda()

def mostrar_ayuda():
    print("\n Guía de uso rápido:")
    print("-------------------------------------------------------------------------")
    print("Opción A: Por comandos")
    print("  python Capa_3/calibracion_multiactivo/calibrar_multiactivo.py <ruta_del_archivo> <nombre_del_activo>")
    print("  Ejemplo: python Capa_3/calibracion_multiactivo/calibrar_multiactivo.py XAGUSD_M15.csv XAGUSD")
    print("\nOpción B: Colocar en carpeta datos")
    print("  Coloque sus archivos .csv o .parquet en Capa_3/calibracion_multiactivo/datos/")
    print("  y ejecute el script sin parámetros: python Capa_3/calibracion_multiactivo/calibrar_multiactivo.py")
    print("-------------------------------------------------------------------------\n")

if __name__ == "__main__":
    main()
