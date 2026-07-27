import os
import sys
import zipfile
import pandas as pd
import numpy as np
from glob import glob

#Configurar codificación de salida
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def ingestar_zips_activo(asset_name: str, directorio_zips: str = None, ruta_destino: str = None):
    print("=========================================================================")
    print(f" CAPA 0: INGESTA Y COMPRESIÓN DE TICKS A M15 - {asset_name.upper()}")
    print("=========================================================================")
    
    ruta_actual = os.path.dirname(os.path.abspath(__file__))
    
    if not directorio_zips:
        directorio_zips = os.path.abspath(os.path.join(ruta_actual, "..", "Datos_Crudos_Zip", asset_name.upper()))
        
    if not os.path.exists(directorio_zips):
        raise FileNotFoundError(f"El directorio de zips no existe: {directorio_zips}")
        
    archivos_zip = sorted(glob(os.path.join(directorio_zips, "*.zip")))
    
    if not archivos_zip:
        raise ValueError(f"No se encontraron archivos .zip en {directorio_zips}")
        
    print(f"• Encontrados {len(archivos_zip)} archivos .zip para procesar.")
    
    lista_m15 = []
    
    for zip_path in archivos_zip:
        try:
            with zipfile.ZipFile(zip_path, 'r') as z:
                # HistData normalmente tiene un solo archivo CSV por zip
                nombre_csv = z.namelist()[0]
                
                # Leer directamente de memoria
                df_mes = pd.read_csv(
                    z.open(nombre_csv), 
                    header=None, 
                    names=['timestamp', 'bid', 'ask', 'vol'],
                    dtype={'timestamp': str, 'bid': float, 'ask': float, 'vol': int}
                )
                
                # Convertir timestamp: formato YYYYMMDD HHMMSSmmm
                # Ejemplo: "20200101 180008183"
                df_mes['timestamp'] = pd.to_datetime(df_mes['timestamp'], format='%Y%m%d %H%M%S%f')
                df_mes.set_index('timestamp', inplace=True)
                
                # Resamplear a M15 usando el Bid (estándar para graficación)
                df_m15 = df_mes['bid'].resample('15min').agg(
                    open='first',
                    high='max',
                    low='min',
                    close='last'
                ).dropna()
                
                lista_m15.append(df_m15)
                print(f"  -> Procesado: {os.path.basename(zip_path)}  Velas M15 extraídas: {len(df_m15)}")
                
        except Exception as e:
            print(f"   Error procesando {os.path.basename(zip_path)}: {e}")
            
    print("• Concatenando todo el histórico...")
    df_completo = pd.concat(lista_m15)
    
    # Asegurar orden
    df_completo.sort_index(inplace=True)
    
    # Calcular retornos
    print("• Calculando log-retornos...")
    df_completo['returns'] = np.log(df_completo['close'] / df_completo['close'].shift(1))
    df_completo.dropna(inplace=True)
    
    if not ruta_destino:
        dir_datos = os.path.abspath(os.path.join(ruta_actual, "..", "datos"))
        os.makedirs(dir_datos, exist_ok=True)
        ruta_destino = os.path.join(dir_datos, f"{asset_name.upper()}_M15_Training.parquet")
        
    print(f"• Guardando Parquet optimizado en: {ruta_destino}...")
    df_completo.to_parquet(ruta_destino, engine='pyarrow', compression='snappy')
    
    print(f" INGESTA COMPLETADA EXITOSAMENTE")
    print(f" • Volumen total de velas M15: {df_completo.shape[0]}")
    print(f" • Ventana temporal: {df_completo.index.min()} a {df_completo.index.max()}")
    print("=========================================================================\n")
    return ruta_destino

if __name__ == "__main__":
    if len(sys.argv) >= 2:
        ingestar_zips_activo(sys.argv[1])
    else:
        print("Uso: python ingestar_zips_histdata.py <nombre_activo>")
