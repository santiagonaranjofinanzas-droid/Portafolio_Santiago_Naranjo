import os
import asyncio
import json
from playwright.async_api import async_playwright
from supabase import create_client, Client
from dotenv import load_dotenv
import datetime
import dateparser
import requests
from ai_service import generate_response
import re

load_dotenv()

#Configuration
URL = os.getenv("CAMPUS_URL", "https://micampusvirtual.espe.edu.ec")
USERNAME = os.getenv("CAMPUS_USER")
PASSWORD = os.getenv("CAMPUS_PASS")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

#--- Helper Functions ---

def clean_subject_name(name: str) -> str:
    """Super aggressive cleaning for subject names."""
    # Remove technical noise
    name = name.replace("\n", " ")
    name = re.sub(r'Nombre del curso', '', name, flags=re.IGNORECASE)
    # Remove any codes like [27817] or 27817- or 202650
    name = re.sub(r'\[\d+\]', '', name)
    name = re.sub(r'\d+[-\s_]*', ' ', name)
    
    # Deduplicate repeating words (case-insensitive)
    words = name.split()
    seen = set()
    unique_words = []
    for w in words:
        # Avoid short noise words or already seen ones
        if len(w) > 2 and w.lower() not in seen:
            unique_words.append(w)
            seen.add(w_lower := w.lower())
        elif len(w) <= 2: # Keep short words like "De", "La" but don't deduplicate aggressively
            unique_words.append(w)
    
    clean = " ".join(unique_words).strip()
    if " - " in clean: clean = clean.split(" - ", 1)[-1]
    return clean.title().strip()

def generate_ai_summary(titulo: str, materia: str, descripcion: str) -> str:
    """Generate an AI summary with better prompting."""
    try:
        if not titulo or not materia: return ""
        # Filter out system titles
        if "bloque" in titulo.lower() or "sección" in titulo.lower(): return ""
        
        prompt = f"""Eres un asistente académico. Resume esta tarea y da 3 pasos clave:
Tarea: {titulo}
Materia: {materia}
Descripción: {descripcion[:800]}
Responde en español, sé directo y usa viñetas."""
        summary = generate_response(prompt)
        return summary.strip() if summary and not summary.startswith("Error") else ""
    except: return ""

def detect_task_type(title: str) -> str:
    k = ["prueba", "examen", "test", "quiz", "control de lectura", "leccion", "evaluación", "cuestionario", "parcial"]
    return "prueba" if any(w in title.lower() for w in k) else "deber"

async def login_moodle(page):
    print(f"[SCRAPER] Navigating to login...")
    try:
        await page.goto(f"{URL}/login/index.php", wait_until="networkidle", timeout=30000)
        if await page.query_selector('.userpicture'): return True
        await page.fill("#username", USERNAME)
        await page.fill("#password", PASSWORD)
        await page.click("#loginbtn")
        await page.wait_for_load_state("networkidle")
        return await page.query_selector('.userpicture') is not None
    except: return False

async def run_scraper():
    if not SUPABASE_URL or not SUPABASE_KEY: return
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            if not await login_moodle(page): return

            # --- PHASE 1: TIMELINE (ROBUST DATES) ---
            print("\n[SCRAPER] PHASE 1: Timeline Sync...")
            await page.goto(f"{URL}/my/", wait_until="networkidle")
            
            try:
                await page.click('[data-region="timeline"] [data-toggle="dropdown"]')
                await page.click('[data-filtername="all"]')
                await page.wait_for_timeout(2000)
            except: pass

            for _ in range(5):
                show_more = await page.query_selector('button[data-action="more-events"]')
                if show_more and await show_more.is_visible():
                    await show_more.click()
                    await page.wait_for_timeout(1500)
                else: break

            timeline_data = {}
            event_links = await page.query_selector_all('[data-region="event-list-item"] .event-name a')
            for link_elem in event_links:
                label = await link_elem.get_attribute("aria-label")
                href = await link_elem.get_attribute("href")
                if label and href and "id=" in href:
                    mid = "".join(filter(str.isdigit, href.split("id=")[1].split("&")[0]))
                    match = re.search(r'(.+) actividad en (.+) est(?:áa) pendiente para (.+)', label)
                    if match:
                        title_t = match.group(1).strip()
                        materia_t = clean_subject_name(match.group(2).strip())
                        date_t = match.group(3).strip()
                        
                        parsed_d = dateparser.parse(date_t, languages=['es'], settings={'PREFER_DATES_FROM': 'future'})
                        timeline_data[mid] = {
                            "titulo": title_t,
                            "materia": materia_t,
                            "fecha_entrega": parsed_d.isoformat() if parsed_d else None,
                            "url": href
                        }

            # --- PHASE 2: FINAL SYNC ---
            print(f"\n[SCRAPER] Processing {len(timeline_data)} robust tasks...")

            for mid, data in timeline_data.items():
                # Filter out junk
                if "bloque" in data["titulo"].lower(): continue

                print(f"--- Processing {mid}: {data['titulo'][:30]} ---")
                await page.goto(data["url"], wait_until="domcontentloaded", timeout=15000)
                
                desc_elem = await page.query_selector("#intro, .box.py-3.generalbox, .instructions")
                description = (await desc_elem.inner_text()) if desc_elem else ""
                
                # Check if it has a date on page if timeline failed
                if not data["fecha_entrega"]:
                    de = await page.query_selector(".activity-dates")
                    if de:
                        dt = await de.inner_text()
                        p = dateparser.parse(dt, languages=['es'], settings={'PREFER_DATES_FROM': 'future'})
                        if p: data["fecha_entrega"] = p.isoformat()

                resumen = generate_ai_summary(data["titulo"], data["materia"], description)
                
                task_data = {
                    "id_moodle": mid,
                    "titulo": data["titulo"],
                    "materia": data["materia"],
                    "descripcion": description[:1200],
                    "estado": "por_empezar",
                    "archivada": False,
                    "fecha_entrega": data["fecha_entrega"],
                    "tipo": detect_task_type(data["titulo"]),
                    "resumen_ia": resumen
                }
                
                try:
                    supabase.table("tareas").upsert(task_data, on_conflict="id_moodle").execute()
                    print(f"  [SYNCED] OK")
                except Exception as e:
                    if "unique constraint" in str(e).lower():
                        task_data["titulo"] = f"{data['titulo']} ({data['materia']})"
                        supabase.table("tareas").upsert(task_data, on_conflict="id_moodle").execute()
                    else: print(f"  [DB-ERROR] {e}")

        finally: await browser.close()

if __name__ == "__main__":
    asyncio.run(run_scraper())
