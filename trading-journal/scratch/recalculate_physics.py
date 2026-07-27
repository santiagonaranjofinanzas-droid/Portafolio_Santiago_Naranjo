#!/usr/bin/env python3
import sqlite3
from datetime import datetime
from pathlib import Path
import sys

import pandas as pd

#Add repo root to path to allow importing backend app modules.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.engine import calculate_trade_physics


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


def parse_time(value):
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace('Z', ''))
    return value


def to_float_or_none(value):
    return None if pd.isna(value) else float(value)


db_path = resolve_db_path()
print(f'Using database: {db_path}')

cols = ['position_id', 'symbol', 'entrytime', 'exittime', 'entryprice', 'exitprice', 'type_op', 'sl', 'netpnl', 'volume']

with sqlite3.connect(str(db_path)) as conn:
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT position_id, symbol, entrytime, exittime, entryprice, exitprice, type_op, sl, netpnl, volume
        FROM tradearchive
        WHERE position_id = 62612639
        """
    )
    row = cursor.fetchone()
    if not row:
        print('Trade 62612639 not found in DB')
        raise SystemExit(1)

    trade_dict = dict(zip(cols, row))
    trade_dict['entrytime'] = parse_time(trade_dict['entrytime'])
    trade_dict['exittime'] = parse_time(trade_dict['exittime'])

    print('=== Trade Details before physics calc ===')
    print(trade_dict)

    print('\nCalculating physics...')
    physics = calculate_trade_physics(trade_dict)
    print('\n=== Calculation Results ===')
    print(f'MAE: {physics[0]}')
    print(f'MFE: {physics[1]}')
    print(f'MAE R-ratio: {physics[2]}')
    print(f'MFE R-ratio: {physics[3]}')
    print(f'TW-MAE R-ratio: {physics[4]}')
    print(f'TW-MFE R-ratio: {physics[5]}')
    print(f'R-Capture Efficiency: {physics[6]}')

    mae, mfe, mae_r, mfe_r, tw_mae_r, tw_mfe_r, efficiency = (
        to_float_or_none(value) for value in physics
    )

    cursor.execute(
        """
        UPDATE tradearchive
        SET mae = ?, mfe = ?, mae_r = ?, mfe_r = ?, tw_mae_r = ?, tw_mfe_r = ?, efficiency = ?
        WHERE position_id = 62612639
        """,
        (mae, mfe, mae_r, mfe_r, tw_mae_r, tw_mfe_r, efficiency),
    )
    conn.commit()
    print('\n[OK] Database updated for trade 62612639.')

    print('\nRecalculating MAE/MFE for all trades in the DB...')
    cursor.execute(
        """
        SELECT position_id, symbol, entrytime, exittime, entryprice, exitprice, type_op, sl, netpnl, volume
        FROM tradearchive
        WHERE type_op IN (0, 1)
        """
    )
    all_rows = cursor.fetchall()

    recalc_count = 0
    for row in all_rows:
        trade = dict(zip(cols, row))
        trade['entrytime'] = parse_time(trade['entrytime'])
        trade['exittime'] = parse_time(trade['exittime'])

        try:
            phys = calculate_trade_physics(trade)
            t_mae, t_mfe, t_maer, t_mfer, t_tw_mae_r, t_tw_mfe_r, t_eff = (
                to_float_or_none(value) for value in phys
            )

            cursor.execute(
                """
                UPDATE tradearchive
                SET mae = ?, mfe = ?, mae_r = ?, mfe_r = ?, tw_mae_r = ?, tw_mfe_r = ?, efficiency = ?
                WHERE position_id = ?
                """,
                (t_mae, t_mfe, t_maer, t_mfer, t_tw_mae_r, t_tw_mfe_r, t_eff, trade['position_id']),
            )
            recalc_count += 1
        except Exception as exc:
            print(f"Error on PID {trade['position_id']}: {exc}")

    conn.commit()
    print(f'[OK] Recalculated and updated {recalc_count} trades in the DB.')

print('\n[OK] DB Cleanup and Recalculation complete.')
