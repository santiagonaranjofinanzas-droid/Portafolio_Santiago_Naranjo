#!/usr/bin/env python3
import subprocess
import re

try:
    # Use powershell to get command line and process info for terminal64
    cmd = 'powershell -Command "Get-CimInstance Win32_Process -Filter \\"Name=\'terminal64.exe\'\\"  Select-Object ProcessId, CommandLine"'
    output = subprocess.check_output(cmd, shell=True).decode('utf-8', errors='ignore')
    print("=== Running MT5 Terminals ===")
    print(output)
except Exception as e:
    print("Error getting process info:", e)
