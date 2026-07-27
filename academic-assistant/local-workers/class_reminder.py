import os
import asyncio
import datetime
from dotenv import load_dotenv
from telegram_notifier import send_notification

load_dotenv()

#Diccionario de clases y enlaces
SCHEDULE = {
    0: {  # Lunes
        "17:00": {"name": "Liderazgo", "link": "https://cedia.zoom.us/j/9771620453"}
    },
    1: {  # Martes
        "17:00": {"name": "Economía Internacional", "link": "https://cedia.zoom.us/j/86307638374"},
        "19:00": {"name": "Finanzas Corporativas y Mercado de Valores", "link": "https://teams.microsoft.com/meet/2946832374372?p=c3WgUYqFcaqguCveKy\nID: 294 683 237 437 2\nPasscode: dC9Lc2Gb"}
    },
    2: {  # Miércoles
        "19:00": {"name": "Economías Innovadoras", "link": "https://teams.microsoft.com/meet/23496449269621?p=KyyMtCOKF6Nr6YcJio\nID: 234 964 492 696 21\nPasscode: Eq32d7nB"}
    },
    3: {  # Jueves
        "17:00": {"name": "Gestión y Emprendimiento", "link": "https://cedia.zoom.us/j/87298006049"},
        "19:00": {"name": "Gestión de la Calidad", "link": "https://us06web.zoom.us/j/89636651652?pwd=QsG66CxRrhcc4kH4W63yTyXb7FStua.1"}
    },
    4: {  # Viernes
        "17:00": {"name": "Diseño y Evaluación de Proyecto", "link": "https://teams.microsoft.com/meet/266096719618997?p=SGWR0i7wtwal1LCv7T\nID: 266 096 719 618 997\nPasscode: xv9t2Xd9"}
    }
}

REMINDER_MINUTES = 15

#Almacenar alertas que ya se enviaron hoy para no repetir
notified_today = set()

async def check_classes():
    now = datetime.datetime.now()
    weekday = now.weekday()
    date_str = now.strftime("%Y-%m-%d")

    if weekday in SCHEDULE:
        day_schedule = SCHEDULE[weekday]
        for time_str, class_info in day_schedule.items():
            # Create datetime object for the class today
            class_time = datetime.datetime.strptime(time_str, "%H:%M").replace(
                year=now.year, month=now.month, day=now.day
            )
            
            time_diff = class_time - now
            minutes_left = time_diff.total_seconds() / 60.0

            # Identifier format: 2026-04-20_17:00
            alert_id = f"{date_str}_{time_str}"

            if 0 < minutes_left <= REMINDER_MINUTES and alert_id not in notified_today:
                msg = (
                    f" *Recordatorio de Clase* \n\n"
                    f"¡Tu clase de *{class_info['name']}* comienza en {int(minutes_left)} minutos ({class_time.strftime('%I:%M %p')})!\n\n"
                    f" *Enlace de acceso:*\n{class_info['link']}"
                )
                await send_notification(msg)
                notified_today.add(alert_id)
                print(f"Sent class reminder for {class_info['name']} at {time_str}")

async def main_loop():
    print("Iniciando Monitor de Clases (Revisión cada 1 min)...")
    while True:
        try:
            # Check classes
            await check_classes()
            
            # Limpiar caché si es un nuevo día
            now = datetime.datetime.now()
            if now.hour == 0 and now.minute <= 5:
                # Keep cache small or clear at midnight
                notified_today.clear()
                
        except Exception as e:
            print(f"Error checking classes: {e}")
            
        # Dormir 60 segundos
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main_loop())
