#!/usr/bin/env python3
import os
import glob

log_dir = r"C:\Users\YOUR_USERNAME\AppData\Roaming\MetaQuotes\Terminal\48C08BACFA9BF7AF04237AACCEC7E873\logs"
log_files = glob.glob(os.path.join(log_dir, "*.log"))

if not log_files:
    print("No log files found in terminal directory.")
    exit(0)

latest_log = max(log_files, key=os.path.getmtime)
print(f"Reading log: {os.path.basename(latest_log)}")

try:
    content = open(latest_log, 'r', encoding='utf-16', errors='ignore').read()
except Exception:
    content = open(latest_log, 'r', encoding='utf-8', errors='ignore').read()

lines = content.splitlines()
print("\nLast 50 lines of MT5 terminal log for Real Terminal:")
for l in lines[-50:]:
    print(l)
