import sys
import os
import sqlite3

#Add scratch path to import phase2_outbox_agent
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scratch"))
import phase2_outbox_agent

def main():
    print("Initializing direct outbox flush...")
    settings = phase2_outbox_agent.load_settings()
    # Override settings to target the local backend
    settings = phase2_outbox_agent.AgentSettings(
        endpoint="http://localhost:8080/api/v1/ingest/trade",
        queue_db_path=settings.queue_db_path,
        queue_dir=settings.queue_dir,
        poll_seconds=settings.poll_seconds,
        request_timeout_seconds=settings.request_timeout_seconds,
        max_attempts=settings.max_attempts,
        backoff_base_seconds=settings.backoff_base_seconds,
        hmac_secret=settings.hmac_secret,
        hmac_key_id=settings.hmac_key_id
    )
    
    print(f"Target endpoint: {settings.endpoint}")
    print(f"Queue DB path: {settings.queue_db_path}")
    
    try:
        conn = sqlite3.connect(settings.queue_db_path)
        print("Connected to database successfully. Flushing outbox...")
        sent, failed = phase2_outbox_agent.flush_outbox(conn, settings)
        print(f"Flush completed: sent={sent}, failed={failed}")
        conn.close()
    except Exception as e:
        print(f"Error during direct flush: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
