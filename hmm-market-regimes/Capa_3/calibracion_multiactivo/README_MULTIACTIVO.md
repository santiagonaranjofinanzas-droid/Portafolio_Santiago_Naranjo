#Guía de Calibración Multiactivo - Sistema Sovereign HMM (30001)

Esta subcarpeta contiene el pipeline adaptado para calibrar los parámetros del modelo **Sovereign HMM (versión 30001)** para otros activos financieros (como el **NAS100**, la **Plata**, divisas, etc.).

El script de calibración preserva de manera exacta la paridad matemática y secuencial de la lógica de reentrenamiento original (diseño de momentos estocásticos MLE y filtro Forward de Hamilton) utilizada para el oro (XAUUSD).

---

## Cómo Utilizar el Pipeline de Calibración

El script [calibrar_multiactivo.py](file:///c:/Users/YOUR_USERNAME/Desktop/Trading/1_#####HMM#####/Capa_3/calibracion_multiactivo/calibrar_multiactivo.py) admite dos modos de uso:

###Opción A: Ejecución Directa por Línea de Comandos (CLI)
Pase la ruta de su archivo de datos (CSV o Parquet) y el nombre del activo como argumentos:
```bash
python Capa_3/calibracion_multiactivo/calibrar_multiactivo.py "ruta/al/archivo_datos.csv" "NAS100"
```

###Opción B: Calibración por Lotes (Batch Mode)
1. Coloque sus archivos de precios (en formato `.csv` o `.parquet`) en la carpeta `Capa_3/calibracion_multiactivo/datos/` (que se crea automáticamente al ejecutar el script por primera vez).
2. Nómbrelos empezando por el activo, por ejemplo: `SILVER_M15.csv` o `NAS100_15M.parquet`.
3. Ejecute el script sin parámetros:
```bash
python Capa_3/calibracion_multiactivo/calibrar_multiactivo.py
```
El pipeline procesará todos los archivos presentes y guardará los resultados con el formato `HMM_Params_15M_{ACTIVO}.csv`.

---

## Formato de Datos de Entrada Soportado

El script es sumamente flexible y detecta de manera inteligente las columnas y separadores. Admite:

1. **Exports Directos de MetaTrader 5 (MT5)**:
   - Formato CSV delimitado por tabuladores o comas.
   - Columnas estándar como `<DATE>`, `<TIME>`, y `<CLOSE>`.
2. **Archivos Parquet**:
   - Columnas `timestamp` y `close`.
3. **Archivos CSV genéricos**:
   - Cualquier archivo que contenga las columnas `close` (precio de cierre) y opcionalmente una columna de tiempo (`timestamp`, `time` o `date`) para ordenación cronológica.

---

## Rationale Cuantitativo: ¿En qué otros activos funciona este sistema?

El modelo **Sovereign HMM 30001** está diseñado bajo la premisa de que los mercados no son estacionarios y alternan entre **regímenes de mercado diferenciados** (tendencias alcistas o bajistas estables, períodos de consolidación de baja volatilidad y expansiones de alta volatilidad con saltos extremos). 

Utiliza una distribución **t-Student** para el ruido del mercado (capturando colas anchas) combinada con una componente de **salto log-normal** (para movimientos atípicos bruscos).

Basado en esta estructura matemática, el sistema es idóneo para los siguientes universos de activos:

###1. Plata (XAGUSD) — *Altamente Recomendado*
- **Comportamiento**: Al igual que el Oro, es un metal precioso que actúa como refugio de valor, pero tiene una beta y volatilidad significativamente mayores.
- **HMM Fit**: Los "saltos" estocásticos (jumps) en la plata son muy frecuentes y violentos. El estimador por momentos del pipeline aislará de manera óptima el parámetro $\lambda$ (tasa de saltos) y la distribución t-Student ($\nu$ grados de libertad) para parametrizar las colas anchas del activo.

###2. NAS100 / US100 (Nasdaq 100) — *Altamente Recomendado*
- **Comportamiento**: Los índices de acciones de crecimiento tecnológico exhiben regímenes cíclicos marcados: largas subidas de volatilidad extremadamente baja (grind alcista) intercaladas con correcciones rápidas y capitulaciones de alta volatilidad (pánico).
- **HMM Fit**: El filtro de Hamilton detecta de forma excelente estas transiciones bruscas de régimen (Bull vs. Bear con cambio de volatilidad). La calibración adaptativa permitirá al EA bloquear las compras rápidamente durante regímenes de pánico bajista.

###3. Petróleo Crudo (WTI / Brent)
- **Comportamiento**: Las commodities energéticas son altamente direccionales y dependientes del ciclo geopolítico y macroeconómico, lo que genera tendencias muy persistentes y saltos debidos a noticias de oferta/demanda.
- **HMM Fit**: Las probabilidades de transición HMM ($P_{Bull}$ y $P_{Bear}$) calibradas en estos activos tienden a ser altas (ej. $>0.95$), lo que significa que una vez que el crudo entra en una tendencia (regímen), tiende a mantenerse en ella por un largo tiempo.

###4. Pares de Divisas Mayores (EURUSD, GBPUSD, USDJPY)
- **Comportamiento**: Los pares de divisas son de naturaleza reversiva a la media en el largo plazo, pero experimentan fuertes tendencias direccionales a mediano plazo cuando cambian los diferenciales de tasas de interés de los bancos centrales.
- **HMM Fit**: Permite distinguir cuándo un par de divisas está consolidando en un rango plano (regimenes neutrales con baja fuerza de señal) frente a impulsos macroeconómicos fuertes.

###5. Bitcoin (BTCUSD)
- **Comportamiento**: Activo con asimetría positiva extrema, fases de acumulación planas y ciclos alcistas explosivos con volatilidad exponencial.
- **HMM Fit**: El componente de saltos captura las velas de liquidación de apalancamiento, y el filtro de Hamilton ayuda a evitar el "ruido" de consolidación lateral. *Nota: Exige spreads y comisiones bajos en el broker para mantener la rentabilidad.*
