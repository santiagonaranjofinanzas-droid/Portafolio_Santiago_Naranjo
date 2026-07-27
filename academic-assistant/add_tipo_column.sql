-- Ejecuta este comando en el editor SQL de tu panel de Supabase
-- para añadir la columna de tipo a la tabla de tareas.

ALTER TABLE tareas ADD COLUMN IF NOT EXISTS tipo TEXT DEFAULT 'deber';

-- Opcional: Actualizar tareas existentes que parecen ser pruebas
UPDATE tareas SET tipo = 'prueba' 
WHERE LOWER(titulo) LIKE '%prueba%' 
   OR LOWER(titulo) LIKE '%examen%' 
   OR LOWER(titulo) LIKE '%control%'
   OR LOWER(titulo) LIKE '%evaluaci%';
