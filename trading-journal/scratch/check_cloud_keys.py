import os
from sqlmodel import Session, create_engine, select
from backend.app.models import ApiKey, Organization
from dotenv import load_dotenv

load_dotenv(dotenv_path='backend/.env')

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

def check_keys():
    with Session(engine) as session:
        orgs = session.exec(select(Organization)).all()
        print(f"Organizations found: {len(orgs)}")
        for org in orgs:
            print(f"Org: {org.id}  Name: {org.name}")
            
        keys = session.exec(select(ApiKey)).all()
        print(f"\nAPI Keys found: {len(keys)}")
        for k in keys:
            print(f"Key: {k.key_secret}  OrgID: {k.organization_id}  Active: {k.is_active}")

if __name__ == "__main__":
    check_keys()
