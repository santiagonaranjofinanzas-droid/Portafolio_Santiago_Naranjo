import os
import asyncio
import json
import logging
import uuid
import requests
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from supabase import create_client, Client
from dotenv import load_dotenv
from ai_service import generate_response
from email_processor import get_unread_emails, classify_with_ai

load_dotenv(override=True)

#Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
if TELEGRAM_TOKEN:
    print(f"[DEBUG] Usando token que termina en: ...{TELEGRAM_TOKEN[-5:]}")
if TELEGRAM_CHAT_ID:
    TELEGRAM_CHAT_ID = int(TELEGRAM_CHAT_ID.strip())
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

#Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

#Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def get_ai_response(prompt: str) -> str:
    """Gets a response from NVIDIA AI API."""
    try:
        res = generate_response(prompt)
        if res and not res.startswith("Error"):
            return res
        return f"Lo siento, hubo un problema con la IA: {res}"
    except Exception as e:
        return f"Error de IA: {e}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initial greeting."""
    user = update.effective_user
    if user.id != TELEGRAM_CHAT_ID:
        logging.warning(f"Unauthorized access attempt from user {user.id}")
        return

    welcome = (
        f"¡Hola {user.mention_html()}!  Soy tu *Asistente Académico ESPE* 2.0.\n\n"
        "Puedo ayudarte a:\n"
        " Ver tus tareas (/tareas)\n"
        " Recomendar por dónde empezar (/recomendar)\n"
        " Distribuir trabajos grupales (/distribuir)\n"
        " Capturar ideas simplemente escribiéndolas."
    )
    await update.message.reply_html(
        welcome,
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("/tareas"), KeyboardButton("/recomendar")],
            [KeyboardButton("/distribuir"), KeyboardButton("/ayuda")]
        ], resize_keyboard=True)
    )

async def view_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists upcoming tasks from Supabase."""
    if update.effective_user.id != TELEGRAM_CHAT_ID: return
    await update.message.reply_chat_action("typing")
    try:
        response = supabase.table("tareas").select("*").eq("archivada", False).order("fecha_entrega", desc=False).execute()
        tasks = response.data

        if not tasks:
            await update.message.reply_text(" ¡No tienes tareas pendientes! Estás al día.")
            return

        msg = " *Tareas Pendientes*\n\n"
        for t in tasks:
            date_str = "Sin fecha"
            if t['fecha_entrega']:
                dt = datetime.fromisoformat(t['fecha_entrega'].replace('Z', ''))
                date_str = dt.strftime("%d/%m")
            
            icon = "" if t['estado'] == 'por_empezar' else ""
            msg += f"{icon} *{t['titulo']}*\n    {date_str}   {t['materia']}\n\n"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f" Error DB: {e}")

async def recommend_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Uses IA to decide which task to start with."""
    if update.effective_user.id != TELEGRAM_CHAT_ID: return
    await update.message.reply_chat_action("typing")
    try:
        response = supabase.table("tareas").select("*").eq("archivada", False).order("fecha_entrega", desc=False).limit(5).execute()
        tasks = response.data

        if not tasks:
            await update.message.reply_text("No hay tareas para analizar.")
            return

        task_summaries = []
        for t in tasks:
            task_summaries.append(f"- {t['titulo']} (Materia: {t['materia']}, Vence: {t['fecha_entrega']})")
        
        prompt = f"""Como mi tutor académico personal de la ESPE, analiza estas tareas y dime cuál me recomiendas empezar hoy y por qué.
Tareas:
{chr(10).join(task_summaries)}
Responde brevemente en español, sé motivador y directo."""

        ai_response = await get_ai_response(prompt)
        await update.message.reply_text(f" *Consejo del Tutor IA*:\n\n{ai_response}", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"Error IA: {e}")

async def check_emails(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Checks for important unread emails."""
    if update.effective_user.id != TELEGRAM_CHAT_ID: return
    await update.message.reply_chat_action("typing")
    try:
        unread = get_unread_emails()
        if not unread:
            await update.message.reply_text(" No hay correos nuevos sin leer.")
            return

        important_emails = []
        for item in unread:
            importance = classify_with_ai(item['subject'], item['body'])
            if importance >= 3:
                important_emails.append(f" *[{importance}/5]* {item['subject']}")
        
        if not important_emails:
            await update.message.reply_text(f" Tienes {len(unread)} correos nuevos, pero ninguno parece crítico.")
            return

        msg = " *Correos Importantes Recientes*\n\n" + "\n".join(important_emails)
        msg += "\n\n_Revisa tu Gmail para más detalles._"
        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f" Error al revisar correos: {e}")

async def distribute_work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Suggests how to split a group task."""
    if update.effective_user.id != TELEGRAM_CHAT_ID: return
    await update.message.reply_text("Dime de qué trata el trabajo grupal y cuántos integrantes son (ej: 'Proyecto de software, 4 personas').")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes natural language messages."""
    if update.effective_user.id != TELEGRAM_CHAT_ID: return
    text = update.message.text
    text_lower = text.lower()
    
    # 1. Check for specific question patterns
    if any(q in text_lower for q in ["que hago", "mis tareas", "deberes"]):
        await view_tasks(update, context)
        return
    
    if any(q in text_lower for q in ["recomienda", "ayuda", "recomiendame", "por cual empiezo"]):
        await recommend_start(update, context)
        return

    if any(q in text_lower for q in ["correo", "email", "mensaje", "llego algo"]):
        await check_emails(update, context)
        return

    # 2. IA Help vs Quick Capture
    if "?" in text or len(text.split()) > 8:
        # It's a conversation/question
        await update.message.reply_chat_action("typing")
        ai_response = await get_ai_response(f"Responde como un asistente académico de la ESPE: {text}")
        await update.message.reply_text(ai_response)
    else:
        # It's a Quick Capture (Short phrase)
        await update.message.reply_chat_action("upload_document")
        default_due_date = (datetime.now() + timedelta(days=7)).isoformat()
        task_data = {
            "id_moodle": f"msg_{uuid.uuid4().hex[:8]}",
            "titulo": text[:50] + ("..." if len(text) > 50 else ""),
            "materia": "General/Telegram",
            "descripcion": text,
            "estado": "por_empezar",
            "archivada": False,
            "fecha_entrega": default_due_date
        }
        try:
            supabase.table("tareas").insert(task_data).execute()
            await update.message.reply_text(f" *Capturado*: '{text}' añadido al Dashboard.", parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(" Error al guardar captura rápida.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays help information."""
    help_text = (
        " *Guía del Asistente Académico*\n\n"
        "/tareas - Lista de deberes pendientes.\n"
        "/recomendar - Planificación inteligente.\n"
        "/distribuir - Repartir carga grupal.\n\n"
        " *Tip*: Si me envías un mensaje corto como 'Hacer mapa mental', lo anotaré como tarea automáticamente."
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

def main():
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN missing.")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tareas", view_tasks))
    app.add_handler(CommandHandler("recomendar", recommend_start))
    app.add_handler(CommandHandler("distribuir", distribute_work))
    app.add_handler(CommandHandler("correos", check_emails))
    app.add_handler(CommandHandler("ayuda", help_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("[LOG] Super Agente de Telegram Iniciado")
    app.run_polling()

if __name__ == "__main__":
    main()
