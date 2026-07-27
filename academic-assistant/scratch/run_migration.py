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

#Try to add the column 'tipo' directly using RPC if available, or just a dummy update to trigger it?
#Actually, the best way to add a column is via the Supabase Dashboard SQL Editor.
#But I'll try to see if I can do it via a common trick or if the user has to do it.

print("Attempting to add 'tipo' column to 'tareas' table...")
try:
    # This is a raw SQL execution via postgrest if enabled (unlikely)
    # Most Supabase projects don't have a public 'execute_sql' RPC for security.
    # We will try a simpler approach: check if we can just perform an update that includes it.
    
    # Wait, if I don't have RPC, I can't run raw DDL from the client.
    # The user should run this in the Supabase Dashboard:
    # ALTER TABLE tareas ADD COLUMN IF NOT EXISTS tipo TEXT DEFAULT 'deber';
    
    print("Please run the following SQL in your Supabase Dashboard SQL Editor:")
    print("ALTER TABLE tareas ADD COLUMN IF NOT EXISTS tipo TEXT DEFAULT 'deber';")
    
except Exception as e:
    print(f"Error: {e}")
