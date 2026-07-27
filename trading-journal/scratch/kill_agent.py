#!/usr/bin/env python3
import subprocess
import os
import signal

try:
    # Use powershell to list processes with cmdline and filter in python
    cmd = 'powershell -Command "Get-CimInstance Win32_Process  Where-Object { $_.Name -eq \'python.exe\' }  Select-Object ProcessId, CommandLine  ConvertTo-Json"'
    output = subprocess.check_output(cmd, shell=True).decode('utf-8', errors='ignore')
    
    if output.strip():
        import json
        data = json.loads(output)
        if isinstance(data, dict):
            data = [data]
            
        for proc in data:
            cmdline = proc.get('CommandLine') or ''
            pid = proc.get('ProcessId')
            if 'phase2' in cmdline:
                print(f"Killing process {pid}: {cmdline}")
                try:
                    os.kill(pid, signal.SIGTERM)
                    print(f"Successfully killed process {pid}")
                except Exception as e:
                    print(f"Failed to kill {pid}: {e}")
                    # Try taskkill
                    os.system(f"taskkill /F /PID {pid}")
except Exception as e:
    print("Error:", e)
