import os
import time
import subprocess
import json
import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv(override=True)

#Configuration
CHECK_INTERVAL = 60  # Check every 60 seconds
SCRAPER_INTERVAL_HOURS = 3
CONFIG_FILE = "automation_config.json"

#Supabase Setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

def get_config():
    """Reads configuration from local file or Supabase."""
    # Default config
    config = {
        "automatizacion_activa": True,
        "ultima_ejecucion_scraper": None,
        "intervalo_horas": SCRAPER_INTERVAL_HOURS
    }
    
    # Try local file first
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                local_config = json.load(f)
                config.update(local_config)
        except:
            pass
            
    # Try Supabase if available (optional sync)
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
            res = supabase.table('sistema_config').select('*').eq('id', 1).execute()
            if res.data:
                config.update(res.data[0])
        except Exception as e:
            # Table might not exist yet, we'll use local file
            pass
            
    return config

def save_config(config):
    """Saves configuration to local file and Supabase."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)
        
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
            # Try to update or skip if table doesn't exist
            supabase.table('sistema_config').upsert(config, on_conflict='id').execute()
        except:
            pass

def run_script(script_name, wait=True):
    """Executes a python script in the .venv."""
    python_exe = os.path.join(".venv", "Scripts", "python.exe")
    if not os.path.exists(python_exe):
        python_exe = "python" # Fallback
        
    print(f"[{datetime.datetime.now()}] Ejecutando {script_name}...")
    try:
        if wait:
            subprocess.run([python_exe, script_name], check=True)
        else:
            subprocess.Popen([python_exe, script_name])
    except Exception as e:
        print(f"Error ejecutando {script_name}: {e}")

def main():
    print("=== ASISTENTE ACADÉMICO: WORKER MAESTRO ===")
    print(f"Iniciado el: {datetime.datetime.now()}")
    
    # Ensure other background bots are running (one-time start)
    # email_checker.py and deadline_monitor.py have their own loops or are monitors
    print("[MASTER] Iniciando bots persistentes...")
    run_script("telegram_bot.py", wait=False)
    run_script("email_checker.py", wait=False) # email_checker has a 10min loop
    run_script("deadline_monitor.py", wait=False)
    run_script("class_reminder.py", wait=False)

    while True:
        try:
            config = get_config()
            
            if not config.get("automatizacion_activa", True):
                print(f"[{datetime.datetime.now()}] Automatización PAUSADA (Parada de emergencia activa).")
                time.sleep(CHECK_INTERVAL)
                continue
                
            # Logic for Scraper (Every 3 hours)
            ultima = config.get("ultima_ejecucion_scraper")
            run_scraper = False
            
            if not ultima:
                run_scraper = True
            else:
                last_time = datetime.datetime.fromisoformat(ultima)
                if last_time.tzinfo is not None:
                    now = datetime.datetime.now(last_time.tzinfo)
                else:
                    now = datetime.datetime.now()
                diff = now - last_time
                if diff.total_seconds() >= (config.get("intervalo_horas", 3) * 3600):
                    run_scraper = True
            
            if run_scraper:
                print(f"[{datetime.datetime.now()}] Iniciando Scraper ESPE (Intervalo cumplido)...")
                run_script("uni_scraper.py", wait=True)
                
                # Update config
                config["ultima_ejecucion_scraper"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                save_config(config)
                print(f"[{datetime.datetime.now()}] Scraper finalizado. Próxima ejecución en {config.get('intervalo_horas', 3)} horas.")
            
            # General health check or other periodic tasks can go here
            
        except Exception as e:
            print(f"ERROR en Master Worker: {e}")
            
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
