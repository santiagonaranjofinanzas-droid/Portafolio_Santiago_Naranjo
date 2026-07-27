import os
import sys

import numpy as np
import pandas as pd

ruta_actual = os.path.dirname(os.path.abspath(__file__))
ruta_raiz = os.path.abspath(os.path.join(ruta_actual, ".."))
ruta_capa2 = os.path.join(ruta_raiz, "Capa_2")
if ruta_raiz not in sys.path:
    sys.path.insert(0, ruta_raiz)
if ruta_capa2 not in sys.path:
    sys.path.insert(0, ruta_capa2)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from Capa_4.sovereign_execution import CFinancialEngine


def _pnl_money(price_diff: float, lot: float, tick_value: float, tick_size: float) -> float:
    return price_diff * lot * (tick_value / tick_size)


def ejecutar_backtest_comercial_capa4():
    ruta_capa2_signals = os.path.join(ruta_capa2, "auditoria_capa2_signals.csv")

    print("=========================================================================")
    print("CAPA 4: BACKTEST ALINEADO CON SOVEREIGN_NORMAL_EXPERT")
    print("=========================================================================")

    if not os.path.exists(ruta_capa2_signals):
        print(f"ERROR: No se encontro el mapa de senales de Capa 2: {ruta_capa2_signals}")
        print("Ejecuta Capa_2/Validar_Capa2.py primero.")
        return

    df = pd.read_csv(ruta_capa2_signals, index_col=0, parse_dates=True)
    close_prices = df["close"].to_numpy(dtype=float)
    high_prices = df["high"].to_numpy(dtype=float)
    low_prices = df["low"].to_numpy(dtype=float)
    regime = df["Regime_Buffer_18"].to_numpy(dtype=int)
    vtv_sigma = df["Vol_Projected_Sigma"].to_numpy(dtype=float)
    ml_strength = df["ML_Master_Strength"].to_numpy(dtype=float)

    balance_inicial = 10000.0
    balance = balance_inicial
    risk_percent = 1.0
    inp_min_strength = 0.35
    inp_vol_multiplier = 2.5
    inp_reward_risk = 2.0
    inp_use_partials = True
    inp_max_lot = 10.0

    point = 0.01
    tick_size = 0.01
    tick_value = 1.0
    spread_price = 0.0

    posicion_activa = None
    precio_entrada = 0.0
    lote_inicial = 0.0
    lote_actual = 0.0
    stop_loss = 0.0
    take_profit = 0.0
    parcial_ejecutado = False
    flujos_realizados = []
    posiciones_cerradas = 0

    for i in range(1, len(df)):
        close_t = close_prices[i]
        high_t = high_prices[i]
        low_t = low_prices[i]

        if posicion_activa is None:
            if regime[i] != 0 and ml_strength[i] >= inp_min_strength:
                trade_type = 1 if regime[i] == 1 else -1
                precio_entrada = close_t
                sl_dist = CFinancialEngine.calculate_volatility_stop(
                    precio_entrada, vtv_sigma[i], inp_vol_multiplier, spread_price
                )
                sl_pts = int(sl_dist / point)
                lote_inicial = CFinancialEngine.calculate_adaptive_lot(
                    balance, risk_percent, sl_pts, tick_value, tick_size, point, inp_max_lot
                )
                lote_actual = lote_inicial
                parcial_ejecutado = False
                if trade_type == 1:
                    posicion_activa = "BUY"
                    stop_loss = precio_entrada - sl_dist
                    take_profit = precio_entrada + sl_dist * inp_reward_risk
                else:
                    posicion_activa = "SELL"
                    stop_loss = precio_entrada + sl_dist
                    take_profit = precio_entrada - sl_dist * inp_reward_risk
            continue

        if posicion_activa == "BUY":
            initial_risk_price = abs(precio_entrada - stop_loss)
            if inp_use_partials and initial_risk_price >= point and not parcial_ejecutado:
                partial_target = precio_entrada + initial_risk_price * (inp_reward_risk / 1.5)
                if high_t >= partial_target:
                    cierre = max(partial_target, close_t)
                    resultado = _pnl_money(cierre - precio_entrada, lote_inicial * 0.70, tick_value, tick_size)
                    balance += resultado
                    flujos_realizados.append(resultado)
                    lote_actual = round(lote_inicial * 0.30, 2)
                    stop_loss = precio_entrada
                    parcial_ejecutado = True
            if low_t <= stop_loss:
                resultado = _pnl_money(stop_loss - precio_entrada, lote_actual, tick_value, tick_size)
                balance += resultado
                flujos_realizados.append(resultado)
                posiciones_cerradas += 1
                posicion_activa = None
            elif high_t >= take_profit:
                resultado = _pnl_money(take_profit - precio_entrada, lote_actual, tick_value, tick_size)
                balance += resultado
                flujos_realizados.append(resultado)
                posiciones_cerradas += 1
                posicion_activa = None

        elif posicion_activa == "SELL":
            initial_risk_price = abs(stop_loss - precio_entrada)
            if inp_use_partials and initial_risk_price >= point and not parcial_ejecutado:
                partial_target = precio_entrada - initial_risk_price * (inp_reward_risk / 1.5)
                if low_t <= partial_target:
                    cierre = min(partial_target, close_t)
                    resultado = _pnl_money(precio_entrada - cierre, lote_inicial * 0.70, tick_value, tick_size)
                    balance += resultado
                    flujos_realizados.append(resultado)
                    lote_actual = round(lote_inicial * 0.30, 2)
                    stop_loss = precio_entrada
                    parcial_ejecutado = True
            if high_t >= stop_loss:
                resultado = _pnl_money(precio_entrada - stop_loss, lote_actual, tick_value, tick_size)
                balance += resultado
                flujos_realizados.append(resultado)
                posiciones_cerradas += 1
                posicion_activa = None
            elif low_t <= take_profit:
                resultado = _pnl_money(precio_entrada - take_profit, lote_actual, tick_value, tick_size)
                balance += resultado
                flujos_realizados.append(resultado)
                posiciones_cerradas += 1
                posicion_activa = None

    trades_arr = np.array(flujos_realizados)
    ganadores = trades_arr[trades_arr > 0]
    perdedores = trades_arr[trades_arr <= 0]
    win_rate = (len(ganadores) / len(trades_arr) * 100.0) if len(trades_arr) > 0 else 0.0
    profit_factor = (np.sum(ganadores) / abs(np.sum(perdedores))) if len(perdedores) > 0 and np.sum(perdedores) != 0 else 1.0

    print(f"Balance final: ${balance:.2f}")
    print(f"Retorno neto: {((balance - balance_inicial) / balance_inicial) * 100.0:.2f}%")
    print(f"Posiciones cerradas: {posiciones_cerradas}")
    print(f"Flujos realizados: {len(flujos_realizados)}")
    print(f"Win rate: {win_rate:.2f}%")
    print(f"Profit factor: {profit_factor:.2f}")
    print("Supuestos simulador: point=0.01, tick_size=0.01, tick_value=1.0, spread_price=0.0")
    print("=========================================================================")


if __name__ == "__main__":
    ejecutar_backtest_comercial_capa4()
