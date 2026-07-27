import os
import sys
from sqlmodel import Session, create_engine, select, SQLModel
from dotenv import load_dotenv

#Add backend to path so 'app' is findable
backend_path = os.path.join(os.getcwd(), "backend")
if backend_path not in sys.path:
    sys.path.append(backend_path)

#Explicitly load .env from backend folder
load_dotenv(os.path.join(backend_path, ".env"))

from app.models import TradeArchive, CapitalLog, Organization, MacroNews, TradeJournal, AccountSnapshot, Mt5Node, ApiKey, IngestionEvent

#Source: Local SQLite (Root folder)
sqlite_url = "sqlite:///black_knight_quant_journal.db"
sqlite_engine = create_engine(sqlite_url)

#Target: Aiven (Read from .env)
supabase_url = os.getenv("DATABASE_URL")
if not supabase_url:
    print("ERROR: DATABASE_URL not found in .env")
    exit(1)

if supabase_url.startswith("postgres://"):
    supabase_url = supabase_url.replace("postgres://", "postgresql://", 1)

supabase_engine = create_engine(supabase_url)

def migrate():
    print(f"Starting migration from SQLite to Aiven...")
    
    try:
        # Create tables in Aiven
        SQLModel.metadata.create_all(supabase_engine)
        print("OK - Tables created/verified in Aiven.")
    except Exception as e:
        print(f"ERROR creating tables: {e}")
        return

    models = [
        Organization, ApiKey, TradeArchive, CapitalLog, 
        MacroNews, TradeJournal, AccountSnapshot, Mt5Node, IngestionEvent
    ]

    with Session(sqlite_engine) as sqlite_session:
        with Session(supabase_engine) as supabase_session:
            for model in models:
                print(f"Migrating {model.__name__}...")
                try:
                    items = sqlite_session.exec(select(model)).all()
                except Exception as e:
                    print(f"  - Table {model.__name__} not found in SQLite yet. Skipping.")
                    continue
                
                if not items:
                    print(f"  - No data found for {model.__name__}")
                    continue

                count = 0
                for item in items:
                    data = item.dict()
                    new_item = model(**data)
                    supabase_session.add(new_item)
                    count += 1
                
                try:
                    supabase_session.commit()
                    print(f"  OK - Migrated {count} items of {model.__name__}")
                except Exception as e:
                    supabase_session.rollback()
                    print(f"  ERROR migrating {model.__name__}: {e}")

    print("\nMigration finished successfully!")

if __name__ == "__main__":
    migrate()
