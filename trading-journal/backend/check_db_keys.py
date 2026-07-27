import os
from sqlmodel import create_engine, Session, select
from app.models import ApiKey

DATABASE_URL = "postgresql+psycopg://avnadmin:AVNS_EWyQlHMAjEZeCy03Npf@pg-2d252eaa-santiagonaranjofinanzas-058f.l.aivencloud.com:23503/defaultdb?sslmode=require"

engine = create_engine(DATABASE_URL)

with Session(engine) as session:
    keys = session.exec(select(ApiKey)).all()
    print("--- DB API KEYS ---")
    if not keys:
        print("NO KEYS FOUND IN DATABASE!")
    for k in keys:
        print(f"ID: {k.id}, Org: {k.organization_id}, Active: {k.is_active}")
        print(f"Key Hash: {k.key_hash}")
        print(f"Key Secret: {k.key_secret}")
        print("-------------------")
