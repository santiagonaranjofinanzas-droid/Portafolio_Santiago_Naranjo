from datetime import datetime
from pathlib import Path
import sqlite3
import sys

import MetaTrader5 as mt5
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.engine import get_trade_m1_data


def resolve_db_path() -> Path:
    candidates = [
        REPO_ROOT / 'black_knight_quant_journal.db',
        REPO_ROOT / 'backend' / 'black_knight_quant_journal.db',
        Path.cwd() / 'black_knight_quant_journal.db',
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError('No se encontró black_knight_quant_journal.db en las rutas esperadas.')


db_path = resolve_db_path()

with sqlite3.connect(str(db_path)) as conn:
    row = conn.execute(
        """
        SELECT position_id, symbol, entrytime, exittime
        FROM tradearchive
        WHERE type_op IN (0, 1)
          AND entrytime IS NOT NULL
          AND exittime IS NOT NULL
        ORDER BY (julianday(exittime) - julianday(entrytime)) DESC
        LIMIT 1
        """
    ).fetchone()

if not row:
    print('No se encontraron trades válidos para probar chunking.')
    raise SystemExit(1)

position_id, symbol, entrytime, exittime = row
entry_time = datetime.fromisoformat(entrytime.replace('Z', '')) if isinstance(entrytime, str) else entrytime
exit_time = datetime.fromisoformat(exittime.replace('Z', '')) if isinstance(exittime, str) else exittime

print(f'Testing trade {position_id} on {symbol}')
print(f'Range: {entry_time} -> {exit_time}')

if not mt5.initialize():
    print('MT5 Init failed')
    raise SystemExit(1)

try:
    rates = get_trade_m1_data(symbol, entry_time, exit_time)
    if not rates:
        print('No data fetched from MT5')
        raise SystemExit(1)

    df = pd.DataFrame(rates)
    if 'time' not in df.columns:
        print('Missing time column in fetched data')
        raise SystemExit(1)

    duplicate_count = int(df.duplicated(subset=['time']).sum())
    df['time'] = pd.to_datetime(df['time'])
    print(f'Rows: {len(df)}')
    print(f'Duplicate timestamps: {duplicate_count}')
    print(f'Min time: {df["time"].min()}')
    print(f'Max time: {df["time"].max()}')
    print(df.head())

    if duplicate_count != 0:
        print('Chunking validation failed: duplicate timestamps found')
        raise SystemExit(1)
finally:
    mt5.shutdown()
