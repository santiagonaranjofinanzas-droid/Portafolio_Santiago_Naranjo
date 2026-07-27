import os
import shutil
import time
from datetime import datetime
from histdata import download_hist_data as dl
from histdata.api import Platform as P, TimeFrame as TF

def descargar_datos():
    # Pares a descargar: 
    # NSXUSD (NAS100)
    # XAGUSD (Plata)
    # EURUSD
    pares = ['nsxusd', 'xagusd', 'eurusd']
    
    anio_inicio = 2020
    anio_actual = datetime.now().year
    mes_actual = datetime.now().month

    # Directorio de salida
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(base_dir, 'Datos_Crudos_Zip')
    os.makedirs(output_dir, exist_ok=True)

    print(f"Iniciando descarga de datos desde {anio_inicio} hasta la actualidad.")
    print(f"Los archivos se guardarán en: {output_dir}")

    for pair in pares:
        pair_dir = os.path.join(output_dir, pair.upper())
        os.makedirs(pair_dir, exist_ok=True)
        
        for year in range(anio_inicio, anio_actual + 1):
            # Determinar hasta qué mes descargar en el año actual
            if year == anio_actual:
                meses_a_descargar = range(1, mes_actual + 1)
            else:
                meses_a_descargar = range(1, 13)
                
            for month in meses_a_descargar:
                print(f"Descargando {pair.upper()} para {year}-{month:02d}...")
                
                try:
                    # Descargar (esto guarda el zip en el directorio de trabajo actual por defecto)
                    zip_path = dl(
                        year=str(year), 
                        month=str(month), 
                        pair=pair, 
                        platform=P.GENERIC_ASCII, 
                        time_frame=TF.TICK_DATA
                    )
                    
                    if zip_path and os.path.exists(zip_path):
                        # Mover al directorio estructurado
                        file_name = os.path.basename(zip_path)
                        dest_path = os.path.join(pair_dir, file_name)
                        shutil.move(zip_path, dest_path)
                        print(f"  -> Guardado: {dest_path}")
                    else:
                        print(f"  -> No se encontró datos para {pair.upper()} en {year}-{month:02d}.")
                        
                except Exception as e:
                    print(f"  -> Error al descargar {pair.upper()} {year}-{month:02d}: {e}")
                
                # Pequeña pausa para no saturar el servidor
                time.sleep(1)

    print("Descarga completada.")

if __name__ == '__main__':
    descargar_datos()
