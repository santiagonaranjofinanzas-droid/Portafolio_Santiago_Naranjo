import os
from sqlmodel import create_engine, Session, select
from app.models import IngestionEvent

DATABASE_URL = "postgresql+psycopg://avnadmin:AVNS_EWyQlHMAjEZeCy03Npf@pg-2d252eaa-santiagonaranjofinanzas-058f.l.aivencloud.com:23503/defaultdb?sslmode=require"
engine = create_engine(DATABASE_URL)

with Session(engine) as session:
    events = session.exec(select(IngestionEvent).order_by(IngestionEvent.id.desc()).limit(5)).all()
    print("--- LATEST INGESTION EVENTS ---")
    if not events:
        print("No events found in DB.")
    for ev in events:
        print(f"[{ev.received_at}] ID: {ev.id}  Status: {ev.status}  Error: {ev.error_message}")
        print(f"Payload: {ev.payload_json}")
        print("-" * 40)
