#Guía de Despliegue de Producción: TSMOM-CFD (v0.9.6)

Este documento detalla los pasos exactos e institucionales para instalar, configurar y poner en marcha el sistema **TSMOM-CFD (v0.9.6)** en la máquina de destino (VPS o PC secundaria).

---

## Requisitos Previos del Sistema

Antes de iniciar el despliegue, asegúrese de cumplir con los siguientes requisitos en el entorno de destino:

*   **Sistema Operativo**: Windows 10/11 o Windows Server (VPS).
*   **Python**: Versión `3.8`, `3.9`, `3.10` o `3.11` (Asegúrese de marcar la casilla **"Add Python to PATH"** durante el proceso de instalación).
*   **Plataforma**: MetaTrader 5 (MT5) instalada y con sesión iniciada en una cuenta real o demo del broker **AXI Pro**.
*   **Conectividad**: Ambos servicios (el servidor de Python y MetaTrader 5) deben residir en la misma máquina física para garantizar una latencia interproceso menor a 1 ms mediante la red loopback local (`127.0.0.1`).

---

## Lista de Verificación de Archivos (Paquete Exportable)

Confirme que la carpeta exportable `TSMOM_Bot` contiene los siguientes elementos críticos:

*   `TSMOM_EA.mq5` – Código fuente del Asesor Experto adaptado a 26 activos.
*   `execution_server.py` – Servidor TCP backend con el motor predictivo LSTM y la lógica de apalancamiento continuo.
*   `lstm_model_dynamic.pt` – Pesos entrenados del modelo LSTM de 4 características.
*   `requirements.txt` – Archivo con dependencias de librerías Python.
*   `run_server.bat` – Script ejecutable por lotes para arrancar el servidor con un clic.
*   `data/` – Carpeta que contiene los datos históricos diarios en formato CSV de los 26 activos.
*   `src/` – Librerías de Python requeridas (`features.py`, `optimization.py`, etc.).

---

## Pasos de Despliegue Paso a Paso

###Paso 1: Instalación de Dependencias de Python

1. Abra una terminal (`CMD` o `PowerShell`) en la ruta de la carpeta `TSMOM_Bot`.
2. Ejecute el comando para instalar las librerías necesarias:
   ```bash
   pip install -r requirements.txt
   ```
   > [!NOTE]
   > Las librerías críticas que se instalarán son `torch` (CPU), `pandas`, `numpy` y `MetaTrader5`.

---

###Paso 2: Configuración y Compilación en MetaTrader 5

1. Abra MetaTrader 5.
2. En el menú superior, vaya a **Archivo**  **Abrir carpeta de datos**.
3. Navegue a la subcarpeta **`MQL5`**  **`Experts`**.
4. Copie el archivo **`TSMOM_EA.mq5`** del paquete exportable y péguelo en esa carpeta.
5. Regrese a MetaTrader 5, abra el panel del **Navegador** (Ctrl+N), haga clic derecho sobre *Asesores Expertos* y seleccione **Actualizar**.
6. Presione **F4** para abrir el **MetaEditor**.
7. En el árbol de directorios del MetaEditor, abra `TSMOM_EA.mq5` y presione **F7** (o el botón **Compilar** en la barra superior).
   > [!IMPORTANT]
   > Verifique en la pestaña *Errores* (abajo) que el archivo compile con `0 error(s), 0 warning(s)`. Esto generará el ejecutable binario `TSMOM_EA.ex5`.

---

###Paso 3: Autorización de Comercio Algorítmico y Sockets

1. En MetaTrader 5, acceda a **Herramientas**  **Opciones** (o presione `Ctrl+O`).
2. Diríjase a la pestaña **Asesores Expertos**.
3. Marque las siguientes casillas obligatoriamente:
   *    **Permitir el comercio de algoritmos** (Allow AlgoTrading).
   *    **Permitir la importación de DLL** (requerido para el manejo nativo de sockets y red en Windows).
   *    **Permitir WebRequest para las URL listadas**: agregue `http://127.0.0.1:5000` y `http://localhost:5000` a la lista de URLs autorizadas.

---

###Paso 4: Colocación y Parámetros del Expert Advisor

1. En la lista de símbolos de MetaTrader 5, asegúrese de agregar los 26 activos específicos de Axi Pro al cuadro de **Observación del Mercado** (Market Watch).
   > [!TIP]
   > Para agregarlos todos, haga clic derecho en el cuadro *Observación del Mercado*, seleccione *Símbolos*, busque la categoría *Cuentas Pro*, seleccione los activos y presione *Mostrar*.
2. Abra un gráfico limpio de cualquier activo en temporalidad **Diaria (D1)**.
3. Arrastre el EA **`TSMOM_EA`** desde el Navegador al gráfico.
4. En la pestaña **Parámetros de Entrada** (Inputs), configure los valores institucionales certificados:
   *   `InpServerIP` = `127.0.0.1` (IP del servidor de ejecución local)
   *   `InpServerPort` = `5000` (Puerto TCP)
   *   `InpRebalanceHour` = `16` y `InpRebalanceMin` = `55` (La hora diaria de consulta de pesos, 4:55 PM hora del servidor de MT5).
   *   `InpRiskFactor` = `1.0` (Multiplicador de riesgo ex-ante. Se fija en 1.0 porque el backend de Python calcula de forma interna el apalancamiento fuzzy continuo óptimo).
   *   `InpRebalanceThreshold` = `0.0150` (Umbral de histéresis de 150 bps para prevenir tradeos redundantes).
   *   `InpMagicNumber` = `30002` (Identificador del bot para evitar interferir con órdenes manuales u otros EAs).
5. Presione **Aceptar**. Verifique que el sombrero en la esquina superior derecha del gráfico esté azul (o aparezca un ícono de reproducción verde en el botón **AlgoTrading** del menú principal de MT5).

---

###Paso 5: Lanzar el Servidor Backend en Python

1. En el Explorador de archivos de Windows, navegue a la carpeta del bot.
2. Ejecute el archivo **`run_server.bat`** haciendo doble clic sobre él.
3. Se abrirá una terminal que mostrará el siguiente log de confirmación:
   ```text
   [*] TSMOM Production Execution Server listening on 127.0.0.1:5000
   ```
4. El servidor permanecerá a la escucha de peticiones entrantes por sockets en segundo plano de manera continua.

---

## Monitoreo y Mantenimiento Diario

1. **Mensaje Diario del Servidor**:
   Cada día a las 16:55 (u hora configurada), el EA conectará por sockets al servidor Python. Podrá observar los logs impresos en la consola de Python:
   ```text
   [*] Accepted connection from 127.0.0.1:xxxx
   Received request: 'GET_WEIGHTS'
   Weights calculated successfully for date: YYYY-MM-DD
   Leverage factor applied: 8.0000 (Current Drawdown: 0.00%, Lock State: False)
   Sent response successfully.
   ```
2. **Logs en MetaTrader 5**:
   Revise la pestaña **Expertos** en la parte inferior de MT5. Debe ver líneas similares a:
   ```text
   TSMOM EA Initialized. Magic Number: 30002
   Rebalance window open. Connecting to Python Execution Server...
   Weights received successfully. Executing rebalance...
   Parsed 26 asset weights.
   Executing Clean Rebalance -> EURUSD.pro  Target: 0.15 lots  Current: 0.0 lots  Order Size: 0.15
   Rebalance cycle completed.
   ```

---

## Solución de Problemas y Manejo de Errores

###Error: `SocketConnect failed: xxxx`
*   **Causa**: El servidor de Python no se está ejecutando o el puerto 5000 está bloqueado por el firewall de Windows.
*   **Solución**: Ejecute `run_server.bat`. Asegúrese de que no haya otro servicio usando el puerto 5000. Si es necesario, autorice el puerto en la configuración del Firewall de Windows.

###Error: `Symbol xxx is not available in MetaTrader 5`
*   **Causa**: El símbolo broker no está en la ventana de Observación del Mercado (Market Watch).
*   **Solución**: Agregue manualmente el símbolo específico en MT5 (v.g. asegúrese de que `EURUSD.pro` o `COPPER.fs` estén visibles y tengan cotizaciones activas).

###Discrepancia en el Lotaje (Lotes incorrectos)
*   **Causa**: Falta de saldo libre o apalancamiento insuficiente en la cuenta para cubrir el margen.
*   **Solución**: Revise la pestaña *Diario* de MT5. Si aparece el error `Not enough money`, reduzca el tamaño del balance o ajuste el parámetro `InpRiskFactor` a un nivel menor (v.g. `0.5` para mitigar el presupuesto de riesgo de forma proporcional).
