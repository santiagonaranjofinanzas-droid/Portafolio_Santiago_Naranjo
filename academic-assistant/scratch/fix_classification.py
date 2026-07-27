import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv('local-workers/.env')

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_type_from_title(title):
    t = title.lower()
    
    # High priority keywords for PRUEBAS
    pruebas_keywords = ["prueba", "examen", "test", "quiz", "control de lectura", "leccion", "lección", "evaluación", "evaluacion", "cuestionario"]
    if any(w in t for w in pruebas_keywords):
        return "prueba"
    
    # Default
    return "deber"

def fix_data():
    print("Fetching all tasks...")
    res = supabase.table("tareas").select("id_moodle, titulo, tipo").execute()
    tasks = res.data or []
    
    count = 0
    for task in tasks:
        current_tipo = task.get("tipo")
        new_tipo = get_type_from_title(task.get("titulo", ""))
        
        if current_tipo != new_tipo:
            print(f"Updating [{task.get('titulo')[:50]}] from {current_tipo} to {new_tipo}")
            supabase.table("tareas").update({"tipo": new_tipo}).eq("id_moodle", task.get("id_moodle")).execute()
            count += 1
            
    print(f"Finished. Updated {count} tasks.")

if __name__ == "__main__":
    fix_data()
