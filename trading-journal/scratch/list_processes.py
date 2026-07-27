#!/usr/bin/env python3
import subprocess

try:
    # Use tasklist to list all running processes
    output = subprocess.check_output("tasklist", shell=True).decode('utf-8', errors='ignore')
    print("=== Running Python/Uvicorn/Next processes ===")
    for line in output.splitlines():
        if "python" in line.lower() or "node" in line.lower():
            print(line)
except Exception as e:
    print("Error listing processes:", e)
