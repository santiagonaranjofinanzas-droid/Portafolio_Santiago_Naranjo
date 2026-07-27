import imaplib
import email
import os
from email.header import decode_header
from dotenv import load_dotenv
from telegram_notifier import send_notification
import asyncio
import time

load_dotenv()

#Configuration
EMAIL_USER = os.getenv("ESPE_EMAIL") or os.getenv("GMAIL_USER")
EMAIL_PASS = os.getenv("ESPE_PASSWORD") or os.getenv("GMAIL_APP_PASS")
IMAP_SERVER = "outlook.office365.com"

async def check_espe_emails():
    """Checks the ESPE email for recent messages from official domains."""
    if not EMAIL_USER or not EMAIL_PASS:
        print("[EMAIL] Skipping: ESPE_EMAIL or ESPE_PASSWORD not set in .env")
        return

    try:
        # Connect to server
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select("inbox")

        # Search for unread emails from espe.edu.ec
        status, messages = mail.search(None, '(UNSEEN FROM "@espe.edu.ec")')
        
        if status != "OK":
            print("[EMAIL] No matching emails found.")
            return

        mail_ids = messages[0].split()
        if not mail_ids:
            print("[EMAIL] No unread ESPE emails.")
            return

        print(f"[EMAIL] Found {len(mail_ids)} unread ESPE emails.")
        
        for m_id in mail_ids:
            # Fetch the email body
            res, msg_data = mail.fetch(m_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    # Decode subject
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")
                    
                    # Get sender
                    from_ = msg.get("From")
                    
                    print(f"  - New email: {subject} (from {from_})")
                    
                    # Notify via Telegram
                    notification = f" *Nuevo Correo ESPE*\n\n*De*: {from_}\n*Asunto*: {subject}\n\n_Revisa tu bandeja de entrada para más detalles._"
                    await send_notification(notification)
                    
            # Mark as read (default if processed, but let's be explicit)
            # mail.store(m_id, '+FLAGS', '\\Seen')

        mail.logout()
    except Exception as e:
        print(f"[EMAIL] Error connecting to ESPE Mail: {e}")
        if "AUTHENTICATIONFAILED" in str(e):
            print("  TIP: Ensure you are using an 'App Password' if MFA is enabled.")

async def main_loop():
    print("[LOG] Monitor de Correo ESPE iniciado (Escaneando cada 10 min)...")
    while True:
        await check_espe_emails()
        # Sleep for 10 minutes
        await asyncio.sleep(600)

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("Monitor detenido.")
