# Guía de Configuración Multicuenta en MT5

Esta guía te explica cómo configurar tus **dos instancias de MT5 (Cuenta Real y Cuenta Demo)** para que envíen sus datos en tiempo real al mismo agente local y se sincronicen de forma automática en tu Dashboard de Black Knight.

---

## ¿Cómo funciona? (La Solución Elegante)
MT5 por seguridad corre en un "sandbox" (solo puede escribir archivos dentro de su propia carpeta de datos, bajo `MQL5\Files`). 

Para evitar usar DLLs inseguras y no tener que correr múltiples agentes de Python, utilizaremos **Junctions (enlaces de directorio) de Windows**. Esto enlazará la carpeta virtual `_journal_data` de cada MT5 a la carpeta física de tu proyecto. Cuando el EA escriba un trade, se guardará directamente en tu proyecto y el Dashboard lo procesará al instante.

---

## Proceso de Configuración (Paso a Paso)

###Paso 1: Obtener la Carpeta de Datos de cada MT5
Debes identificar las rutas exactas de ambas instancias de MT5.

1. Abre tu **MT5 de Cuenta Real**.
2. Ve al menú superior: **Archivo (File)  Abrir Carpeta de Datos (Open Data Folder)**.
3. Se abrirá el Explorador de Windows. Copia la ruta de la barra de direcciones superior (ej: `C:\Users\YOUR_USERNAME\AppData\Roaming\MetaQuotes\Terminal\3B8D65C1702B23F1C281F8D98C127C34`).
4. Anota esta ruta como tu **`RUTA_REAL`**.
5. Cierra el MT5 Real.
6. Ahora abre tu **MT5 de Cuenta Demo** y repite el proceso para obtener su carpeta de datos. Anótala como tu **`RUTA_DEMO`**.
7. Cierra el MT5 Demo.

---

###Paso 2: Instalar y Compilar el EA en ambas instancias
Para **ambas** instancias de MT5 (Real y Demo), haz lo siguiente:

1. Ve a la carpeta de datos que encontraste en el paso anterior.
2. Navega a `MQL5\Experts\`.
3. Copia el archivo **`Black_Knight_Quant_Reporter.mq5`** (está en la raíz de tu proyecto) y pégalo dentro de esa carpeta `MQL5\Experts\`.
4. Abre el **MetaEditor** en ese MT5 (presiona `F4` o ve a *Herramientas  MetaEditor*).
5. En el navegador izquierdo de MetaEditor, abre `Black_Knight_Quant_Reporter.mq5`.
6. Presiona **F5** (o haz clic en **Compilar** arriba). Asegúrate de que termine sin errores ("compilation completed successfully").

---

###Paso 3: Crear los Enlaces en Windows (Directory Junctions)
Este paso conecta los sandboxes de ambos MT5 con tu proyecto central.

1. Abre el menú Inicio de Windows, escribe **cmd** (Símbolo del sistema) y ábrelo.
2. Ejecuta los siguientes dos comandos. **¡Reemplaza `RUTA_REAL` y `RUTA_DEMO` con las rutas que copiaste en el Paso 1!**

>  **IMPORTANTE:** Si dentro de `MQL5\Files` en tus carpetas de datos de MT5 ya existe una carpeta llamada `_journal_data`, **bórrala primero** antes de ejecutar los comandos para evitar conflictos.

```cmd
:: Enlazar el MT5 de Cuenta Real
mklink /j "RUTA_REAL\MQL5\Files\_journal_data" "c:\Users\YOUR_USERNAME\Desktop\Trading\Proyecto Jorunal\Journal_py_original\_journal_data"

:: Enlazar el MT5 de Cuenta Demo
mklink /j "RUTA_DEMO\MQL5\Files\_journal_data" "c:\Users\YOUR_USERNAME\Desktop\Trading\Proyecto Jorunal\Journal_py_original\_journal_data"
```

####Ejemplo Real de cómo se vería:
```cmd
mklink /j "C:\Users\YOUR_USERNAME\AppData\Roaming\MetaQuotes\Terminal\3B8D65C1702B23F1C281F8D98C127C34\MQL5\Files\_journal_data" "c:\Users\YOUR_USERNAME\Desktop\Trading\Proyecto Jorunal\Journal_py_original\_journal_data"
```

Deberías ver un mensaje en la consola confirmando: 
`Junction created for ... <<===>> ...`

---

###Paso 4: Configurar y Cargar el EA en los Gráficos
Ahora que las carpetas están enlazadas, carga el EA en cada MT5:

1. Abre tu **MT5 Real** y tu **MT5 Demo**.
2. En cada uno, abre cualquier gráfico vacío (por ejemplo, EURUSD M1).
3. Busca `Black_Knight_Quant_Reporter` en la lista de asesores expertos (Navegador) y arrástralo al gráfico.
4. En la pestaña **Común (Common)** de la configuración del EA, activa:
   * **Permitir Trading Algorítmico (Allow Algo Trading)**
   * **Permitir importación de DLL (Allow DLL imports)** (requerido por MT5 por seguridad)
5. En la pestaña **Parámetros de Entrada (Inputs)**:
   * **`InpOutboxPath`**: Asegúrate de que diga `_journal_data/outbox_queue/` (debe ser la misma ruta relativa en ambos).
   * **`InpFullHistory`**: Establécelo en `true` para sincronizar todo el historial de trades al iniciar.
   * **`InpUseCheckpoint`**: Establécelo en `true` (esto evitará que al reiniciar el EA se vuelvan a mandar todos los trades históricos, mejorando drásticamente el rendimiento).
6. Presiona **Aceptar (OK)**.
7. Asegúrate de que el botón **Algo Trading** en la barra superior de MT5 esté en **Verde/Activado**.

---

## ¡Listo para Usar!

1. Inicia el Dashboard del proyecto ejecutando el archivo **`BlackKnight_Dashboard.bat`** en la carpeta raíz y seleccionando la opción `1`.
2. Una vez que se abra el navegador en `http://localhost:3000`, verás el selector de cuentas en la barra superior (Top Bar).
3. **Modo Automático (Auto-Switch):** Por defecto, el Dashboard mostrará la cuenta que haya recibido el trade o snapshot más reciente.
4. **Fijar Cuenta:** Puedes hacer clic en el menú desplegable y seleccionar manualmente tu cuenta **Real** o **Demo** para evaluar su rendimiento por separado.
