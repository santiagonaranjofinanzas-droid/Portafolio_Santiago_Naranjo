import os
import imaplib
import email
from email.header import decode_header
import requests
import json
from dotenv import load_dotenv
from ai_service import generate_response
from telegram_notifier import send_notification
import asyncio

load_dotenv()

#Configuration
EMAIL = os.getenv("GMAIL_USER")
PASSWORD = os.getenv("GMAIL_APP_PASS")
IMAP_SERVER = "imap.gmail.com"

def get_unread_emails():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL, PASSWORD)
        mail.select("inbox")

        status, messages = mail.search(None, 'UNSEEN')
        email_ids = messages[0].split()
        
        emails_to_process = []
        for e_id in email_ids[-5:]:  # Process last 5 unread for safety
            res, msg = mail.fetch(e_id, "(RFC822)")
            for response in msg:
                if isinstance(response, tuple):
                    msg = email.message_from_bytes(response[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")
                    
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode()
                                break
                    else:
                        body = msg.get_payload(decode=True).decode()
                    
                    emails_to_process.append({"subject": subject, "body": body})
        
        mail.logout()
        return emails_to_process
    except Exception as e:
        print(f"Error checking emails: {e}")
        return []

def classify_with_ai(subject, body):
    prompt = f"""
    Clasifica la importancia del siguiente correo académico del 1 al 5.
    1: Spam o informativo irrelevante.
    5: Tarea urgente, examen, o cambio de horario crítico.
    
    Responde ÚNICAMENTE con el número.
    
    Asunto: {subject}
    Contenido: {body[:500]}
    """
    
    try:
        class_str = generate_response(prompt, system_prompt="Eres un clasificador de importancia de correos. Responde solo con un número del 1 al 5.")
        if class_str:
            class_str = class_str.strip()
            return int(class_str[0]) if class_str[0].isdigit() else 1
        return 1
    except Exception as e:
        print(f"AI classification failed: {e}")
        return 1

async def process_emails():
    print("Checking for new emails...")
    unread = get_unread_emails()
    for item in unread:
        importance = classify_with_ai(item['subject'], item['body'])
        print(f"Email: {item['subject']}  Importance: {importance}")
        
        if importance >= 4:
            alert = f" *Prioridad Alta ({importance})*\n {item['subject']}\n\nRevisa tu bandeja de entrada pronto."
            await send_notification(alert)

if __name__ == "__main__":
    asyncio.run(process_emails())
