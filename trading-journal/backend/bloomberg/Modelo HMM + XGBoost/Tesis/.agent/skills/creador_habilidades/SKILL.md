---
name: creador-habilidades
description: Esta habilidad permite al asistente crear nuevas habilidades (skills) en idioma español siguiendo la estructura y estándares oficiales de Antigravity.
---

#Creador de Habilidades

Esta habilidad dota al asistente de la capacidad de expandir sus propias funcionalidades mediante la creación de nuevas carpetas de habilidades.

##Instrucciones para el Asistente

Al usar esta habilidad para crear una nueva habilidad, sigue estos pasos:

1. **Estructura de Directorio**: Crea una nueva carpeta en `.agent/skills/[nombre-de-la-habilidad]`.
2. **Archivo Principal**: Genera un archivo `SKILL.md` dentro de esa carpeta.
3. **YAML Frontmatter**: El `SKILL.md` debe comenzar con un bloque YAML que contenga:
   - `name`: Identificador único (minúsculas, guiones en lugar de espacios).
   - `description`: Una descripción clara en tercera persona que explique cuándo usar la habilidad.
4. **Cuerpo del Markdown**: Define las instrucciones detalladas, patrones de diseño, conveciones y flujos de trabajo específicos de la habilidad.
5. **Idioma**: Todas las instrucciones y descripciones dentro de la habilidad deben estar en **español**.

##Convenciones de Nomenclatura

- Directorios: `serpiente_case` o `kebab-case`.
- Identificador de Skill: `kebab-case`.
- Títulos: "Sentence case" o "Title Case" en español.

##Ejemplo de uso

Si el usuario dice "Crea una habilidad para analizar balances financieros", esta habilidad debe guiarte para crear:
`.agent/skills/analisis_financiero/SKILL.md` con las reglas específicas de análisis de balances.
