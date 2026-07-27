import os
import json
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv('local-workers/.env')

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

res = supabase.table("tareas").select("*").limit(1).execute()
with open("scratch/schema.json", "w", encoding="utf-8") as f:
    json.dump(list(res.data[0].keys()), f, indent=2)
