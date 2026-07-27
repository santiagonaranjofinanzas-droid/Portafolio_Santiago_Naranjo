import os
import asyncio
import json
import logging
import requests
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from supabase import create_client, Client
from dotenv import load_dotenv
from ai_service import generate_response

load_dotenv()

#Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
if TELEGRAM_CHAT_ID:
    TELEGRAM_CHAT_ID = int(TELEGRAM_CHAT_ID.strip())
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

    await update.message.reply_html(
        rf"¡Hola {user.mention_html()}!  Soy tu *Asistente Académico ESPE* virtual.",
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
        # Fetch tasks not archived, ordered by deadline
        response = supabase.table("tareas").select("*").eq("archivada", False).order("fecha_entrega", desc=False).execute()
        tasks = response.data

        if not tasks:
            await update.message.reply_text(" ¡No tienes tareas pendientes! Estás al día.")
            return

        msg = " *Tareas Pendientes*\n\n"
        for t in tasks:
            date_str = "Sin fecha"
            if t['fecha_entrega']:
                dt = datetime.fromisoformat(t['fecha_entrega'])
                date_str = dt.strftime("%d/%m %H:%M")
            
            icon = "" if t['estado'] == 'por_empezar' else ""
            msg += f"{icon} *{t['titulo']}*\n    {date_str}   {t['materia']}\n\n"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f" Error consultando base de datos: {e}")

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
        
        prompt = f"""Como mi tutor académico, analiza estas 5 tareas y dime cuál me recomiendas empezar hoy y por qué. Considera la cercanía de la fecha. Sea breve y motivador.
Tareas:
{chr(10).join(task_summaries)}"""

        ai_response = await get_ai_response(prompt)
        await update.message.reply_text(f" *Recomendación del Tutor AI*:\n\n{ai_response}", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"Hubo un problema analizando tus tareas: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes natural language messages."""
    if update.effective_user.id != TELEGRAM_CHAT_ID: return
    text = update.message.text.lower()
    
    # Simple shortcuts
    if "que tengo que hacer" in text or "tareas" in text:
        await view_tasks(update, context)
        return
    
    if "recomienda" in text or "por cual empiezo" in text:
        await recommend_start(update, context)
        return

    # Use AI for everything else
    await update.message.reply_chat_action("typing")
    ai_response = await get_ai_response(f"Responde brevemente como un asistente académico de la universidad ESPE de Ecuador: {update.message.text}")
    await update.message.reply_text(ai_response)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help info."""
    help_text = """
 *Guía del Asistente*:
/tareas - Ver lo que tienes pendiente.
/recomendar - Deja que la IA te diga por dónde empezar.
/distribuir - Pídeme ayuda para repartir un trabajo grupal.
    
También puedes hablarme normalmente, como: "¿Qué tareas tengo hoy?" o "¿Cómo hago un resumen?".
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

def run_agent():
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN no configurado.")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tareas", view_tasks))
    app.add_handler(CommandHandler("recomendar", recommend_start))
    app.add_handler(CommandHandler("ayuda", help_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print(" Agente de Telegram en ejecución...")
    app.run_polling()

if __name__ == "__main__":
    run_agent()
