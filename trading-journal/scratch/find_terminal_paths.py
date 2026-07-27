#!/usr/bin/env python3
import os
import glob

base_dir = r"C:\Users\YOUR_USERNAME\AppData\Roaming\MetaQuotes\Terminal"
terminals = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d)) and len(d) == 32]

print("Scanning terminals by root logs:")
for t in terminals:
    t_path = os.path.join(base_dir, t)
    
    # Search main logs
    log_dir = os.path.join(t_path, "logs")
    log_files = glob.glob(os.path.join(log_dir, "*.log"))
    recent_log_content = ""
    if log_files:
        latest_log = max(log_files, key=os.path.getmtime)
        try:
            recent_log_content = open(latest_log, 'r', encoding='utf-16', errors='ignore').read()
        except Exception:
            try:
                recent_log_content = open(latest_log, 'r', encoding='utf-8', errors='ignore').read()
            except Exception:
                pass
    
    print(f"Terminal: {t}")
    if "60300368" in recent_log_content or "Axi-US51-Live" in recent_log_content:
        print("  ==> This terminal is connected to REAL account 60300368 / Axi-US51-Live!")
    if "10035063" in recent_log_content or "Axi-US50-Demo" in recent_log_content:
        print("  ==> This terminal is connected to DEMO account 10035063 / Axi-US50-Demo!")

