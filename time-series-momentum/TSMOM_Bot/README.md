#TSMOM Bot - Carpeta de Despliegue de Producción (v0.9.6)

Esta carpeta contiene el entorno de ejecución ligero y autónomo del sistema **DMN-CFD (v0.9.6)** diseñado para ser transferido y ejecutado en una computadora secundaria o VPS de menor potencia.

La lógica cuantitativa compleja e inferencia se ejecutan en Python localmente, mientras que MetaTrader 5 recibe los pesos objetivo listos y se encarga exclusivamente de la colocación de órdenes a través del Expert Advisor.

---

##Estructura de la Carpeta

* `TSMOM_EA.mq5`: Asesor Experto en MQL5. Contiene el Magic Number de control fijado en `30002` y la lógica de rebalanceo inteligente de 150 bps.
* `execution_server.py`: Servidor de sockets de Python que calcula los pesos a partir del modelo entrenado y los datos históricos.
* `lstm_model_dynamic.pt`: Pesos del modelo LSTM entrenados en la computadora principal.
* `run_server.bat`: Ejecutable para arrancar el servidor en Windows con un doble clic.
* `requirements.txt`: Dependencias requeridas de Python.
* `data/`: Contiene los CSVs históricos de precios diarios.
* `src/`: Lógica interna de características y modelos (simplificada, sin código de entrenamiento).

---

##Requisitos Previos

En la computadora de destino, asegúrate de tener instalado:
1. **Python 3.8 - 3.11** (se recomienda agregar Python al PATH de Windows durante la instalación).
2. **MetaTrader 5 Terminal** del broker de CFD/Forex respectivo.

---

##Instrucciones de Instalación y Despliegue

###Paso 1: Instalar dependencias de Python
Abre una terminal (CMD o PowerShell) en esta carpeta y ejecuta:
```bash
pip install -r requirements.txt
```

###Paso 2: Configurar el Expert Advisor en MetaTrader 5
1. Copia el archivo `TSMOM_EA.mq5` a la carpeta de datos de MetaTrader 5 (`MQL5/Experts`). Puedes abrir esta carpeta desde el terminal MT5 yendo a `Archivo` -> `Abrir carpeta de datos`, y navegando a `MQL5/Experts`.
2. En MetaTrader 5, abre el panel de opciones (`Herramientas` -> `Opciones` -> `Asesores Expertos`).
   - Activa la opción **"Permitir el comercio de algoritmos"** (Allow AlgoTrading).
   - Activa **"Permitir WebRequest para las URL listadas"** y agrega `http://127.0.0.1:5000` (o `http://localhost:5000`).
3. Abre el **MetaEditor** (F4 en MT5), abre el archivo `TSMOM_EA.mq5` y compílalo presionando **F7**. Debe compilarse sin errores (se creará el archivo `TSMOM_EA.ex5`).
4. Arrastra el EA `TSMOM_EA` desde el navegador a cualquier gráfico D1 en MT5 y asegúrate de que el botón **"AlgoTrading"** en el panel superior de MetaTrader 5 esté verde.

###Paso 3: Arrancar el Servidor de Ejecución
Haz doble clic sobre el archivo `run_server.bat` o abre una consola y ejecuta:
```bash
python execution_server.py
```
El servidor levantará un socket de escucha en el puerto `5000` (`127.0.0.1:5000`).

Cada día a la hora configurada en el EA (e.g., 4:55 PM EST), el EA en MQL5 consultará los pesos objetivo al servidor Python, evaluará el umbral de 150 bps comparándolos contra el peso real de la cuenta y ejecutará los rebalanceos necesarios con el identificador único `30002`.
