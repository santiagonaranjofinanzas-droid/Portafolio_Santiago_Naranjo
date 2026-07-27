import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv('local-workers/.env')

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def detect_task_type(title: str) -> str:
    t = title.lower()
    if any(w in t for w in ["prueba", "examen", "test", "evaluaci", "quiz", "control", "leccion", "lección"]):
        return "prueba"
    return "deber"

try:
    # Fetch all tasks
    res = supabase.table("tareas").select("id, id_moodle, titulo, tipo").execute()
    tasks = res.data
    
    print(f"Found {len(tasks)} tasks.")
    updated = 0
    for task in tasks:
        current_type = task.get("tipo")
        expected_type = detect_task_type(task["titulo"])
        
        if current_type != expected_type:
            print(f"Updating '{task['titulo']}' from {current_type} to {expected_type}")
            supabase.table("tareas").update({"tipo": expected_type}).eq("id", task["id"]).execute()
            updated += 1
            
    print(f"Updated {updated} tasks successfully.")
except Exception as e:
    print(f"Error: {e}")
