---
name: arquitecto-visual-quant
description: Especialista en estética y diseño de interfaces financieras de alta precisión. Responsable de garantizar que el Dashboard y las visualizaciones cumplan con el estándar institucional Bloomberg-Stripe.
---

#Arquitecto Visual Quant

Esta habilidad se encarga de la dirección de arte y diseño de interfaz (UI) para herramientas de análisis cuantitativo. Su objetivo es proyectar confianza, precisión y sofisticación técnica.

##Principios de Diseño (El Estándar "Quant")

1. **Sofisticación Institucional**:
   - Evoca la autoridad de una terminal de Bloomberg combinada con la modernidad de Stripe o Vercel.
   - Evita elementos visuales innecesarios; cada píxel debe tener un propósito funcional o informativo.

2. **Modo Oscuro (Dark Mode) Nativo**:
   - **Fondo**: Usa paletas de grises antracita profundos (`#0B0E11`, `#121212`) o negros mate.
   - **Acentos**: Usa colores eléctricos o neón con extrema moderación para señales críticas:
     - **Verde Neón**: `Risk-Off` / Compra / Ganancia.
     - **Azul Eléctrico**: Información / Ejecución en curso.
     - **Dorado / Ambar**: Alertas / `Hedge` parcial.
     - **Rojo Coral**: `Risk-On` / Peligro / Cobertura Total.

3. **Tipografía de Precisión**:
   - **UI General**: Usa fuentes Sans-Serif limpias y modernas (Inter, Roboto, Outfit).
   - **Datos y Tickers**: Usa fuentes monoespaciadas (JetBrains Mono, Fira Code, Space Mono) para todos los valores numéricos, tablas de datos y códigos de activos. Esto garantiza la alineación perfecta de las cifras.

4. **Densidad de Datos Elegante**:
   - Capacidad de mostrar múltiples paneles (Rendimiento, Drawdown, Heatmaps) simultáneamente mediante un "layout" de rejilla (Grid).
   - **Glassmorphism**: Aplica desenfoques de fondo sutiles y bordes finos semi-transparentes para separar secciones.
   - **Micro-interacciones**: Las transiciones deben ser instantáneas pero fluidas, reforzando la sensación de una herramienta de alta frecuencia.

##Guía de Estilos para Streamlit/Web

- **Sidebar**: Fondo ligeramente más claro que el principal para generar profundidad.
- **Widgets**: Bordes con radios pequeños (4px-8px) para un look profesional y "hermético".
- **Contenedores**: Usa sombras sutiles o bordes de 1px en lugar de bordes gruesos.
