import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv('local-workers/.env')

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Credentials missing")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    # Test if 'tipo' column exists by selecting it
    res = supabase.table("tareas").select("tipo").limit(1).execute()
    print("Column 'tipo' already exists")
except Exception as e:
    print(f"Column 'tipo' might be missing: {e}")
    print("Attempting to add it via a dummy upsert (this usually fails if column missing)")
    try:
        # This will fail if 'tipo' doesn't exist
        supabase.table("tareas").upsert({"id_moodle": "test_column", "tipo": "deber"}).execute()
        print("Upsert succeeded, column exists!")
    except Exception as e2:
        print(f"Column definitely missing or error: {e2}")
