# Comando de Exportación de Tesis a Microsoft Word
# Optimizado para Windows PowerShell y Pandoc con procesamiento de citas.

# 1. Asegurarse de estar en el directorio raíz del proyecto
# cd c:\Users\NuevoAdmin\Desktop\Tesis

# 2. Comando de ejecución de Pandoc
# Este comando realiza las siguientes tareas:
# - Lee el archivo Markdown de la tesis.
# - Utiliza el motor --citeproc para procesar las citas del archivo .bib.
# - Utiliza el idioma español para las etiquetas generadas (bibliografía, etc.).
# - Genera un archivo .docx de salida.

pandoc Tesis_Final.md --citeproc --bibliography=references.bib --csl=https://raw.githubusercontent.com/citation-style-language/styles/master/apa.csl --metadata lang=es-ES -o Tesis_Final.docx

Write-Host "Exportación completada: Tesis_Final.docx" -ForegroundColor Green
