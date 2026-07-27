import re

with open("run_backtest.py", "r", encoding="utf-8") as f:
    rb = f.read()

#Fix the missing global_trials_sr
if "global_trials_sr = []" not in rb:
    rb = rb.replace("validation_logs = []", "global_trials_sr = []\n    validation_logs = []")

with open("run_backtest.py", "w", encoding="utf-8") as f:
    f.write(rb)
print("global_trials_sr initialization fixed.")
