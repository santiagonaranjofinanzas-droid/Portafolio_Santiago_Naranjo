import os
import asyncio
from supabase import create_client, Client
from dotenv import load_dotenv
import datetime
import json
from telegram_notifier import send_notification

load_dotenv(override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
NOTIFIED_FILE = "notified_tasks.json"

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Warning: Supabase credentials not found. Monitor exiting.")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def load_notified():
    if os.path.exists(NOTIFIED_FILE):
        with open(NOTIFIED_FILE, "r") as f:
            return json.load(f)
    return {}

def save_notified(data):
    with open(NOTIFIED_FILE, "w") as f:
        json.dump(data, f)

async def check_deadlines():
    notified_data = load_notified()
    
    # Fetch active tasks with deadlines
    response = supabase.table("tareas").select("*").eq("archivada", False).execute()
    tasks = response.data
    
    now = datetime.datetime.now(datetime.timezone.utc)
    
    for task in tasks:
        if not task.get("fecha_entrega"):
            continue
            
        due_date = datetime.datetime.fromisoformat(task["fecha_entrega"].replace("Z", "+00:00"))
        time_left = due_date - now
        hours_left = time_left.total_seconds() / 3600
        
        task_id = task["id_moodle"]
        task_notifs = notified_data.get(task_id, {})
        
        titulo = task.get("titulo", "Tarea")
        materia = task.get("materia", "General")
        
        # 24 Hour Warning
        if 2 <= hours_left <= 24 and not task_notifs.get("24h"):
            msg = f" *Alerta 24h*: '{titulo}' de {materia} vence pronto. ¡No lo dejes para última hora!"
            await send_notification(msg)
            task_notifs["24h"] = True
            print(f"Sent 24h alert for {task_id}")
            
        # 10 Minute Warning for Exams/Controls
        is_exam = any(kw in titulo.lower() for kw in ["prueba", "examen", "control de lectura", "leccion", "lección"])
        if is_exam and 0 < hours_left <= 0.17 and not task_notifs.get("10m"): # 0.17h is ~10.2 mins
            msg = f" *RECORDATORIO PRÓXIMO*: Tienes un *{titulo}* de {materia} en 10 minutos. ¡Prepárate!"
            await send_notification(msg)
            task_notifs["10m"] = True
            print(f"Sent 10m alert for {task_id}")
            
        # 2 Hour Warning (Critical)
        elif 0 < hours_left < 2 and not task_notifs.get("2h"):
            msg = f" *CRÍTICO*: '{titulo}' de {materia} vence en menos de 2 horas. Entrégalo YA."
            await send_notification(msg)
            task_notifs["2h"] = True
            print(f"Sent 2h alert for {task_id}")
            
        notified_data[task_id] = task_notifs
        
    save_notified(notified_data)

async def main_loop():
    print("Iniciando Monitor de Vencimientos (Revisión cada 30 min)...")
    while True:
        try:
            await check_deadlines()
        except Exception as e:
            print(f"Error checking deadlines: {e}")
            
        # Sleep for 1 minute
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main_loop())
