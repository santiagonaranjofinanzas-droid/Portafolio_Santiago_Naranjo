import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    try:
        supabase.storage.create_bucket("documentos_espe", {"public": True})
        print("Bucket 'documentos_espe' creado exitosamente.")
    except Exception as e:
        print(f"Nota: El bucket puede que ya exista o hubo un error: {e}")
else:
    print("Faltan credenciales.")
