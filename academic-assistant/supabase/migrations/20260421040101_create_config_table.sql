-- Tabla de configuración del sistema
CREATE TABLE IF NOT EXISTS public.sistema_config (
    id int8 PRIMARY KEY DEFAULT 1,
    automatizacion_activa boolean DEFAULT true,
    ultima_ejecucion_scraper timestamptz,
    intervalo_horas int4 DEFAULT 3,
    CONSTRAINT single_row CHECK (id = 1)
);

-- Habilitar RLS
ALTER TABLE public.sistema_config ENABLE ROW LEVEL SECURITY;

-- Políticas de acceso
CREATE POLICY "Acceso público lectura" ON public.sistema_config FOR SELECT USING (true);
CREATE POLICY "Permitir actualización a autenticados" ON public.sistema_config FOR UPDATE USING (true);

-- Insertar fila inicial si no existe
INSERT INTO public.sistema_config (id, automatizacion_activa, intervalo_horas)
VALUES (1, true, 3)
ON CONFLICT (id) DO NOTHING;
