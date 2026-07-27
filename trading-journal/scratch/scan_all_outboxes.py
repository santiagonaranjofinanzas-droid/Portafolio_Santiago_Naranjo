#!/usr/bin/env python3
import os
import glob

base_dir = r"C:\Users\YOUR_USERNAME\AppData\Roaming\MetaQuotes\Terminal"
terminals = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d)) and len(d) == 32]

print("Scanning outbox queues:")
for t in terminals:
    path = os.path.join(base_dir, t, "MQL5", "Files", "_journal_data", "outbox_queue")
    if os.path.exists(path):
        json_files = glob.glob(os.path.join(path, "*.json"))
        other_files = os.listdir(path)
        print(f"Terminal {t}:")
        print(f"  Path exists: {path}")
        print(f"  JSON files count: {len(json_files)}")
        print(f"  All files: {other_files}")
    else:
        pass

conn = None
