import sqlite3
import json
import os
import subprocess
import sys

db_path = "_journal_data/outbox.db"

def fix_db():
    print(f"Opening outbox database at: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Fetch all dead events
    cursor.execute("SELECT event_id, payload_json FROM outbox_events WHERE status = 'dead'")
    dead_events = cursor.fetchall()
    print(f"Found {len(dead_events)} dead events in outbox.db")
    
    fixed_count = 0
    for event_id, payload_json in dead_events:
        try:
            payload = json.loads(payload_json)
            changed = False
            if "gross_pnl" not in payload:
                payload["gross_pnl"] = payload.get("netpnl", 0.0)
                changed = True
            if "exit_reason" not in payload:
                payload["exit_reason"] = 0
                changed = True
            
            if changed:
                new_payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
                cursor.execute(
                    "UPDATE outbox_events SET payload_json = ?, status = 'pending', attempts = 0, next_retry_at = 0, last_error = NULL WHERE event_id = ?",
                    (new_payload_json, event_id)
                )
                fixed_count += 1
        except Exception as e:
            print(f"Error fixing event {event_id}: {e}")
            
    conn.commit()
    conn.close()
    print(f"Successfully fixed and queued {fixed_count} events in outbox.db")

def run_outbox_agent():
    print("Running outbox agent to flush the queued events...")
    # Set environment variables for the agent to target the local backend
    env = os.environ.copy()
    env["BK_AGENT_ENDPOINT"] = "http://localhost:8080/api/v1/ingest/trade"
    env["BK_AGENT_DB_PATH"] = db_path
    
    # Run outbox agent once
    agent_path = os.path.join(os.getcwd(), "scratch", "phase2_outbox_agent.py")
    res = subprocess.run(
        [sys.executable, agent_path, "--once"],
        env=env,
        capture_output=True,
        text=True
    )
    print("Outbox agent stdout:")
    print(res.stdout)
    if res.stderr:
        print("Outbox agent stderr:")
        print(res.stderr)

if __name__ == "__main__":
    fix_db()
    run_outbox_agent()
