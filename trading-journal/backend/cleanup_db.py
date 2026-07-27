import os
from sqlmodel import Session, create_engine, text
from dotenv import load_dotenv

#Cargar variables de entorno
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print(" Error: DATABASE_URL no encontrada en el entorno.")
    exit(1)

engine = create_engine(DATABASE_URL)

def cleanup():
    with Session(engine) as session:
        print("--- Iniciando limpieza de base de datos de produccion ---")
        
        # Tablas a limpiar
        tables = ["tradearchive", "ingestionevent"]
        
        for table in tables:
            try:
                # Usamos DELETE para limpiar datos
                session.execute(text(f"DELETE FROM {table}"))
                print(f"DONE: Tabla '{table}' limpiada.")
            except Exception as e:
                print(f"ERROR al limpiar '{table}': {e}")
        
        session.commit()
        print("\nBase de datos lista para una sincronizacion limpia.")

if __name__ == "__main__":
    cleanup()
