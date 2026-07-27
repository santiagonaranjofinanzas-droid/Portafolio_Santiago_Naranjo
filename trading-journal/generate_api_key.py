import os
import sys

#Add backend to path so 'app' is findable
backend_path = os.path.join(os.getcwd(), "backend")
if backend_path not in sys.path:
    sys.path.append(backend_path)

from app.models import ApiKey, Organization
from app.database import engine, create_db_and_tables
from sqlmodel import Session, select
import secrets
import hashlib

def generate_api_key(org_name: str = "Black Knight Default"):
    # Ensure tables exist
    create_db_and_tables()
    
    with Session(engine) as session:
        # 1. Ensure Org exists
        org = session.exec(select(Organization).where(Organization.name == org_name)).first()
        if not org:
            org = Organization(name=org_name, slug="default")
            session.add(org)
            session.commit()
            session.refresh(org)
            print(f"OK - Created Organization: {org_name} (ID: {org.id})")

        # 2. Generate Key
        key_id = "BK_" + secrets.token_hex(8).upper()
        key_secret = secrets.token_urlsafe(32)
        
        new_key = ApiKey(
            organization_id=org.id,
            key_id=key_id,
            key_hash=hashlib.sha256(key_id.encode()).hexdigest()[:12], # Small hash for UI display
            key_secret=key_secret,
            is_active=True
        )
        
        session.add(new_key)
        session.commit()
        
        print("\n" + "="*50)
        print("--- BLACK KNIGHT API KEY GENERATED ---")
        print("="*50)
        print(f"Key ID:     {key_id}")
        print(f"Key Secret: {key_secret}")
        print("="*50)
        print("!!! GUARDAR EL SECRET! No se puede recuperar despues.")
        print("Utiliza el 'Key ID' en tu MetaTrader si el backend lo solicita.")
        print("="*50 + "\n")

if __name__ == "__main__":
    generate_api_key()
