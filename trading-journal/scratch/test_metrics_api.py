#!/usr/bin/env python3
import urllib.request
import json
import traceback

url = "http://127.0.0.1:8080/api/v1/metrics?days=365&account_login=10035063&server_name=Axi-US50-Demo"
headers = {"X-BK-Org-Id": "1"}  # Or whatever header is needed to auth or bypass. Let's see.
req = urllib.request.Request(url)

try:
    with urllib.request.urlopen(req, timeout=5) as response:
        data = json.loads(response.read().decode('utf-8'))
        print("=== Metrics API Response ===")
        print("Net Profit:", data.get("summary", {}).get("net_profit"))
        print("Win Rate:", data.get("perf", {}).get("win_rate"))
        print("Payoff Ratio:", data.get("perf", {}).get("payoff"))
        print("Max Drawdown (Cash):", data.get("perf", {}).get("max_drawdown_cash"))
        print("Sharpe Ratio:", data.get("summary", {}).get("sharpe"))
        print("Is Normal:", data.get("quant", {}).get("is_normal"))
except Exception as e:
    traceback.print_exc()
