import pandas as pd
import numpy as np
import glob
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def crear_lago_datos_m15():
    # 1. CONFIGURACIÓN DE RUTAS HISTÓRICAS
    base_path = r"C:\Users\YOUR_USERNAME\Desktop\Trading\1_#####HMM#####\gold_data_parquet"
    search_pattern = os.path.join(base_path, "year=*", "month=*", "*.parquet")
    output_master_file = r"C:\Users\YOUR_USERNAME\Desktop\Trading\1_#####HMM#####\XAUUSD_M15_Training.parquet"
    
    print("=========================================================================")
    print(" PIPELINE CAPA 0: CONSOLIDACIÓN DE LAGO DE DATOS QUANT (M15)")
    print("=========================================================================")
    
    # Buscar todos los archivos mensuales/quincenales de ticks
    all_files = glob.glob(search_pattern)
    if not all_files:
        print(f" CRÍTICO: No se encontraron archivos Parquet en la ruta: {base_path}")
        return
        
    print(f" Se detectaron {len(all_files)} archivos de ticks listos para compresión.")
    
    ohlc_list = []
    
    # 2. BUCLE PROCESADOR DE ALTA EFICIENCIA (STREAMING AGGREGATION)
    for idx, file_path in enumerate(sorted(all_files)):
        try:
            # Cargamos exclusivamente las columnas necesarias para no desbordar la memoria RAM
            df_ticks = pd.read_parquet(file_path, columns=['timestamp', 'bid'])
            df_ticks['timestamp'] = pd.to_datetime(df_ticks['timestamp'])
            
            # Agregación temporal instantánea en el buffer local usando la punta BID (estándar MT5)
            df_m15 = df_ticks.groupby(pd.Grouper(key='timestamp', freq='15min')).agg(
                open=('bid', 'first'),
                high=('bid', 'max'),
                low=('bid', 'min'),
                close=('bid', 'last')
            ).dropna() # Eliminamos horas sin cotización (pausas de mercado / fines de semana)
            
            ohlc_list.append(df_m15)
            print(f"   [{idx+1}/{len(all_files)}] Saneado con éxito: {os.path.basename(file_path)}  Velas: {len(df_m15)}")
            
        except Exception as e:
            print(f"    ERROR procesando el archivo {os.path.basename(file_path)}: {str(e)}")
            
    # 3. CONSOLIDACIÓN DE LA MATRIZ MAESTRA
    print("\n Combinando buffers y limpiando solapamientos temporales...")
    df_global = pd.concat(ohlc_list, axis=0)
    
    # Eliminar registros duplicados en las fronteras exactas de las particiones
    df_global = df_global.loc[~df_global.index.duplicated(keep='first')]
    df_global = df_global.sort_index()
    
    # 4. EXTRACCIÓN DE LOG-RETORNOS (Materia prima cuántica de Sovereign Core)
    # Fórmula: r_t = ln(Close_t / Close_{t-1})
    df_global['returns'] = np.log(df_global['close'] / df_global['close'].shift(1))
    df_global = df_global.dropna() # Purgar la primera vela de la historia que queda con NaN
    
    # 5. ALMACENAMIENTO BINARIO OPTIMIZADO (LAGO DE DATOS LOCAL)
    print(f" Guardando archivo maestro en formato Parquet...")
    df_global.to_parquet(output_master_file, engine='pyarrow', compression='snappy')
    
    # 6. AUDITORÍA FIN DE FASE
    print("\n=========================================================================")
    print(" CAPA 0 COMPLETADA CON ÉXITO")
    print("=========================================================================")
    print(f" • Destino del Lago de Datos: {output_master_file}")
    print(f" • Volumen Total de Velas M15: {df_global.shape[0]}")
    print(f" • Ventana Temporal: Muestras desde {df_global.index.min()} hasta {df_global.index.max()}")
    print(f" • Estabilidad Numérica (NaNs remanentes): {df_global.isnull().values.any()}")
    print("\n Estadísticas Descriptivas de los Retornos:")
    print(df_global['returns'].describe())
    print("=========================================================================\n")

if __name__ == "__main__":
    crear_lago_datos_m15()
