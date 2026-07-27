import MetaTrader5 as mt5
from datetime import datetime, timedelta
import pandas as pd

if not mt5.initialize():
    print("MT5 init failed")
    exit(1)

from_date = datetime(2026, 4, 1)
to_date = datetime.now() + timedelta(days=1)
deals = mt5.history_deals_get(from_date, to_date)
if not deals:
    print("No deals found")
    mt5.shutdown()
    exit(1)

pos_deals = {}
for deal in deals:
    d = deal._asdict()
    pid = d.get('position_id')
    if pid:
        pos_deals.setdefault(pid, []).append(d)

bot_positions = {}
for pid, p_deals in pos_deals.items():
    has_magic = any(d.get('magic') == 30001 for d in p_deals)
    if not has_magic:
        continue
    exits = [d for d in p_deals if d.get('entry') in (1, 2) and d.get('type') in (0, 1)]
    if not exits:
        continue
    bot_positions[pid] = p_deals

partial_close_positions = []
for pid, p_deals in bot_positions.items():
    exits = [d for d in p_deals if d.get('entry') in (1, 2) and d.get('type') in (0, 1)]
    if len(exits) > 1:
        partial_close_positions.append((pid, p_deals))

total_actual = 0.0
total_hypo = 0.0
improved_count = 0
worsened_count = 0

print("=== DETALLE COMPACTO DE POSICIONES CON PARCIALES ===")
for pid, p_deals in partial_close_positions:
    p_deals.sort(key=lambda x: x.get('time'))
    entries = [d for d in p_deals if d.get('entry') == 0 and d.get('type') in (0, 1)]
    exits = [d for d in p_deals if d.get('entry') in (1, 2) and d.get('type') in (0, 1)]
    
    if not entries or not exits:
        continue
        
    entry_deal = entries[0]
    final_exit_deal = exits[-1]
    
    symbol = entry_deal['symbol']
    entry_price = entry_deal['price']
    final_exit_price = final_exit_deal['price']
    type_op = entry_deal['type']
    
    total_volume_in = sum(d['volume'] for d in entries)
    actual_net = sum(d['profit'] for d in exits) + sum(d['commission'] for d in p_deals) + sum(d['swap'] for d in p_deals)
    
    sym_info = mt5.symbol_info(symbol)
    contract_size = sym_info.trade_contract_size if sym_info else 100.0
    
    if type_op == 0: # Buy
        hypo_raw_profit = (final_exit_price - entry_price) * total_volume_in * contract_size
    else: # Sell
        hypo_raw_profit = (entry_price - final_exit_price) * total_volume_in * contract_size
        
    hypo_net = hypo_raw_profit + sum(d['commission'] for d in p_deals) + sum(d['swap'] for d in p_deals)
    diff = hypo_net - actual_net
    
    total_actual += actual_net
    total_hypo += hypo_net
    
    if diff > 0:
        improved_count += 1
    elif diff < 0:
        worsened_count += 1
        
    print(f"Pos ID: {pid}  {symbol}  {'Buy' if type_op == 0 else 'Sell'}  Vol: {total_volume_in:.2f}  Act: {actual_net:+.2f}  Hyp: {hypo_net:+.2f}  Diff: {diff:+.2f}")

print("\n=== RESUMEN COMPARATIVO (WHAT-IF) BOT 30001 ===")
print(f"Total de posiciones con parciales analizadas: {len(partial_close_positions)}")
print(f"  Posiciones que hubieran MEJORADO (mayor ganancia/menor pérdida): {improved_count}")
print(f"  Posiciones que hubieran EMPEORADO (menor ganancia/mayor pérdida): {worsened_count}")
print(f"\nResultado Económico Acumulado de estas posiciones:")
print(f"  PnL Neto Real Obtenido (Con Parciales): ${total_actual:,.2f}")
print(f"  PnL Neto Hipotético (Sin Parciales, saliendo al final): ${total_hypo:,.2f}")
print(f"  Impacto Neto de la estrategia: ${total_hypo - total_actual:+,.2f}")

mt5.shutdown()
