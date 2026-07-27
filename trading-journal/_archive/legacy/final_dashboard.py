import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta, time as dt_time, date
import io # Necesario para la exportación a Excel/CSV
import time # Necesario para el bucle de actualización en vivo
#Nota: La librería MetaTrader5 no funciona en entornos nube (Sandbox/Linux) sin Wine.
#Este código asume ejecución local en Windows con terminal MT5 instalada.
import MetaTrader5 as mt5
from scipy.stats import skew, kurtosis
import os
import json
import uuid
import calendar


# CONFIGURACIÓN & ESTILOS (PREMIUM DARK AESTHETIC - RESTAURADO)
st.set_page_config(page_title="Micro-Fund Audit Tool", layout="wide", page_icon="")

#--- LÓGICA DE CONTROL DE ESTADO (TOP LEVEL) ---
if st.session_state.get('force_toggle_on', False):
    st.session_state['toggle_live'] = True 
    st.session_state['force_toggle_on'] = False 

#Callback para transiciones limpias
def on_menu_change():
    target_page = st.session_state.main_nav
    if target_page == "Monitor en Vivo (Riesgo)":
        st.session_state['toggle_live'] = False
        st.session_state['live_starting_up'] = True
        st.session_state['force_toggle_on'] = False
    else:
        st.session_state['toggle_live'] = False
        st.session_state['live_starting_up'] = False
        st.session_state['force_toggle_on'] = False

#CSS Avanzado: Estilo "Dark Glass" & Tipografía Inter (RESTAURADO)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');

    /* --- GLOBAL THEME --- */
    .stApp {
        background-color: #0F1116; /* Negro Matte Profundo */
        font-family: 'Inter', sans-serif;
    }
    
    h1, h2, h3, h4, h5, h6, p {
        font-family: 'Inter', sans-serif !important;
    }

    /* --- WHITE-LABEL: OCULTAR BRANDING STREAMLIT --- */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stAppDeployButton {display: none !important;}
    .stAppHeader {display: none !important;}
    header[data-testid="stHeader"] {display: none !important;}
    div[data-testid="stAppDeployButton"] {display: none !important;}

    /* --- SIDEBAR --- */
    section[data-testid="stSidebar"] {
        background-color: #0d1117;
        border-right: 1px solid #30363d;
    }
    
    /* TITULO PRINCIPAL (SIDEBAR) */
    .main-header {
        font-size: 24px;
        font-weight: 800;
        background: linear-gradient(90deg, #60A5FA, #A78BFA);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 5px;
        letter-spacing: -0.5px;
    }
    .sub-header {
        font-size: 11px;
        color: #64748B;
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 1.5px;
        margin-bottom: 25px;
        display: block;
    }
    
    /* --- MENÚ DE NAVEGACIÓN (RADIO BUTTONS CUSTOM) --- */
    .stRadio > div[role="radiogroup"] {
        background-color: transparent;
        gap: 8px;
        margin-top: 0px;
    }

    /* 1. Ocultar SOLO el círculo (punto rojo/radio default) */
    .stRadio > div[role="radiogroup"] > label > div:first-of-type {
        display: none !important;
    }
    
    /* 2. Ocultar textos de ayuda molestos (Keyboard shortcuts, etc.) */
    .stRadio div[data-testid="stCaptionContainer"] {
        display: none !important;
    }
    .stRadio div[data-testid="InputInstructions"] {
        display: none !important;
    }
    
    /* 3. Estilo Base del Botón (Contenedor) */
    .stRadio > div[role="radiogroup"] > label {
        background: rgba(255, 255, 255, 0.0); /* Transparente por defecto */
        padding: 12px 12px;
        border-radius: 6px;
        border: 1px solid transparent;
        transition: all 0.2s ease;
        color: #94A3B8 !important; /* Gris medio */
        font-weight: 500;
        font-size: 14px;
        cursor: pointer;
        display: flex;
        align-items: center;
        position: relative;
        overflow: hidden;
    }

    /* 4. Hover (Efecto sutil al pasar el mouse) */
    .stRadio > div[role="radiogroup"] > label:hover {
        background: rgba(255, 255, 255, 0.03);
        color: #E2E8F0 !important;
    }
    
    /* 5. ESTADO SELECCIONADO (Active) */
    .stRadio > div[role="radiogroup"] > label:has(input:checked) {
        background: rgba(59, 130, 246, 0.1);
        border: 1px solid rgba(59, 130, 246, 0.2);
        color: #60A5FA !important; /* Azul claro */
        font-weight: 600;
    }

    /* 6. Indicador Lateral (Barra Azul) */
    .stRadio > div[role="radiogroup"] > label:has(input:checked)::before {
        content: "";
        position: absolute;
        left: 0;
        top: 10%;
        bottom: 10%;
        width: 3px;
        background: #3B82F6;
        border-radius: 0 4px 4px 0;
    }
    
    /* Ajuste del texto interno para alineación */
    .stRadio > div[role="radiogroup"] > label > div[data-testid="stMarkdownContainer"] {
        margin-left: 8px;
        line-height: 1.2;
    }
    
    /* Forzar visibilidad del texto del label principal */
    .stRadio > div[role="radiogroup"] > label p {
        display: block !important;
        margin: 0;
        font-size: 14px !important;
    }

    /* --- BOTÓN SINCRONIZAR (GRADIENTE AZUL-MORADO) --- */
    div.stButton > button {
        background: linear-gradient(90deg, #60A5FA 0%, #A78BFA 100%);
        color: white;
        border: none;
        padding: 12px 28px;
        border-radius: 8px;
        font-weight: 700;
        transition: all 0.3s ease;
        box-shadow: 0 4px 14px rgba(96, 165, 250, 0.3);
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
    }
    div.stButton > button:hover {
        background: linear-gradient(90deg, #3B82F6 0%, #8B5CF6 100%);
        transform: translateY(-1px);
        box-shadow: 0 6px 20px rgba(96, 165, 250, 0.4);
        color: white !important;
        border-color: transparent !important;
    }
    div.stButton > button:active {
        transform: translateY(1px);
    }

    /* --- WRAPPERS / CONTAINERS (BOXES) --- */
    .box {
        background-color: #1A202C; /* Gris Azulado Oscuro */
        border: 1px solid #2D3748;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.15);
        margin-bottom: 24px;
    }
    
    .box-header {
        color: #F7FAFC;
        font-size: 18px;
        font-weight: 700;
        margin-bottom: 20px;
        padding-bottom: 12px;
        border-bottom: 1px solid #2D3748;
        letter-spacing: -0.5px;
        display: flex;
        align-items: center;
    }
    
    /* Bordes acentuados superiores */
    .box-primary { border-top: 4px solid #3B82F6; }
    .box-warning { border-top: 4px solid #F59E0B; }
    .box-danger   { border-top: 4px solid #EF4444; }
    .box-success { border-top: 4px solid #10B981; }

    /* --- METRIC CARDS (PREMIUM GLASS-GRADIENTS) --- */
    .small-box {
        border-radius: 16px;
        position: relative;
        display: block;
        margin-bottom: 20px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.4);
        padding: 24px;
        overflow: hidden;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        border: 1px solid rgba(255,255,255,0.08); /* Borde de cristal */
        color: white;
        backdrop-filter: blur(12px); /* Glassmorphism */
        -webkit-backdrop-filter: blur(12px);
    }
    .small-box:hover {
        transform: translateY(-4px);
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
    }
    .small-box .inner h3 {
        font-size: 36px;
        font-weight: 800;
        margin: 0;
        color: white;
        letter-spacing: -1px;
        line-height: 1.2;
    }
    .small-box .inner p {
        font-size: 13px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
        opacity: 0.85;
        margin-top: 6px;
    }
    .small-box .icon {
        position: absolute;
        top: 50%;
        right: 20px;
        transform: translateY(-50%);
        font-size: 50px;
        opacity: 0.15;
        color: white;
        transition: all 0.3s ease;
    }
    .small-box:hover .icon {
        transform: translateY(-50%) scale(1.1);
        opacity: 0.25;
    }

    /* Gradientes de Cristal (Semi-transparentes) */
    .bg-blue   { background: linear-gradient(135deg, rgba(30, 58, 138, 0.7) 0%, rgba(59, 130, 246, 0.7) 100%); }
    .bg-green  { background: linear-gradient(135deg, rgba(6, 78, 59, 0.7) 0%, rgba(16, 185, 129, 0.7) 100%); }
    .bg-yellow { background: linear-gradient(135deg, rgba(120, 53, 15, 0.7) 0%, rgba(245, 158, 11, 0.7) 100%); }
    .bg-red    { background: linear-gradient(135deg, rgba(127, 29, 29, 0.7) 0%, rgba(239, 68, 68, 0.7) 100%); }
    .bg-purple { background: linear-gradient(135deg, rgba(76, 29, 149, 0.7) 0%, rgba(139, 92, 246, 0.7) 100%); }
    .bg-aqua   { background: linear-gradient(135deg, rgba(21, 94, 117, 0.7) 0%, rgba(6, 182, 212, 0.7) 100%); }

    /* --- INFO BOXES --- */
    .info-box {
        display: flex;
        background-color: #1A202C;
        border: 1px solid #2D3748;
        border-radius: 12px;
        margin-bottom: 20px;
        overflow: hidden;
        align-items: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.2);
    }
    .info-box-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 80px;
        height: 100%;
        min-height: 90px;
        font-size: 32px;
        color: white;
    }
    .info-box-content {
        padding: 15px 20px;
        flex: 1;
    }
    .info-box-text {
        text-transform: uppercase;
        color: #A0AEC0;
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    .info-box-number {
        display: block;
        font-weight: 700;
        font-size: 24px;
        color: #F7FAFC;
    }

    /* --- TABLE STYLING --- */
    div[data-testid="stTable"], div[data-testid="stDataFrame"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* ESTILOS EXTRA PARA JOURNAL (NOTION-LIKE) */
    .journal-card {
        background-color: #1A202C;
        border: 1px solid #2D3748;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        transition: transform 0.2s;
    }
    .journal-card:hover {
        border-color: #4A5568;
        transform: translateY(-2px);
    }
    .journal-tag {
        display: inline-block;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 600;
        margin-right: 6px;
        text-transform: uppercase;
    }
    .tag-win { background-color: rgba(16, 185, 129, 0.2); color: #6EE7B7; }
    .tag-loss { background-color: rgba(239, 68, 68, 0.2); color: #FCA5A5; }
    .tag-neu { background-color: rgba(99, 179, 237, 0.2); color: #90CDF4; }
    
    /* NAV BUTTONS STYLE (STEALTH - GREY & TRANSPARENT) */
    /* Targetizamos botones específicos dentro del journal para que sean grises y sin fondo */
    /* EXCLUIMOS los botones primarios (Guardar/Sincronizar) para no romper su estilo */
    div[data-testid="stExpanderDetails"] button:not([kind="primary"]) {
        background-color: transparent !important;
        background: transparent !important;
        border: none !important;
        color: rgba(255, 255, 255, 0.4) !important; /* Gris transparente inicial */
        box-shadow: none !important;
        font-size: 24px !important;
        padding: 0px 10px !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    
    /* Hover State: Se vuelven más sólidos y crecen */
    div[data-testid="stExpanderDetails"] button:not([kind="primary"]):hover {
        color: rgba(255, 255, 255, 0.9) !important;
        background-color: transparent !important;
        border-color: transparent !important;
        transform: scale(1.25);
    }

    /* Active/Focus State: Eliminar feedback azul nativo de Streamlit */
    div[data-testid="stExpanderDetails"] button:not([kind="primary"]):active,
    div[data-testid="stExpanderDetails"] button:not([kind="primary"]):focus {
        background-color: transparent !important;
        color: #FFFFFF !important;
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
    }
    
    /* Intentamos forzar estilos globales para componentes internos de Streamlit */
    div[data-testid="stDataFrame"] div[role="row"] {
        background-color: #1A202C !important;
        color: #E2E8F0 !important;
    }
    
    th {
        background-color: #2D3748 !important;
        color: #CBD5E0 !important;
        font-weight: 600 !important;
        border-bottom: 1px solid #4A5568 !important;
    }
    td {
        color: #E2E8F0 !important;
        border-bottom: 1px solid #2D3748 !important;
        background-color: #1A202C !important; 
    }
    tr:hover td {
        background-color: #232B3A !important;
    }
    </style>
""", unsafe_allow_html=True)

#==============================================================================
# LÓGICA FINANCIERA
#==============================================================================

def calculate_trade_physics(row):
    """Cálculo MAE/MFE M1"""
    if pd.isna(row['entrytime']) or pd.isna(row['exittime']):
        return pd.Series([np.nan, np.nan, np.nan, np.nan])
    
    # NOTA: copy_rates_range puede ser lento si se consultan muchos datos.
    rates = mt5.copy_rates_range(row['symbol'], mt5.TIMEFRAME_M1, row['entrytime'], row['exittime'])
    
    if rates is None or len(rates) == 0:
        trade_high = max(row['entryprice'], row['exitprice'])
        trade_low = min(row['entryprice'], row['exitprice'])
    else:
        trade_high = max(rates['high'].max(), row['entryprice'], row['exitprice'])
        trade_low = min(rates['low'].min(), row['entryprice'], row['exitprice'])
    
    if row['type_op'] == 0: # Buy
        mfe = trade_high - row['entryprice']
        mae = trade_low - row['entryprice'] 
    else: # Sell
        mfe = row['entryprice'] - trade_low
        mae = row['entryprice'] - trade_high
        
    risk_price = abs(row['entryprice'] - row['sl']) if row['sl'] > 0 else 0
    if risk_price > 0:
        mae_r = mae / risk_price
        mfe_r = mfe / risk_price
    else:
        mae_r = np.nan
        mfe_r = np.nan
        
    return pd.Series([mae, mfe, mae_r, mfe_r])

def determine_session(dt):
    h = dt.hour
    if 22 <= h or h < 8: return "TK (Tokyo)"
    elif 8 <= h < 13: return "LD (London)"
    elif 13 <= h < 22: return "NY (New York)"
    return "Other"

def get_day_name_es(dt):
    days = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}
    return days.get(dt.weekday(), "")

@st.cache_data(show_spinner=False, ttl=300)
def get_mt5_data(days_back=365):
    if not mt5.initialize(): return None, None, None, f"Error MT5: {mt5.last_error()}"
    
    acc = mt5.account_info()
    current_bal = acc.balance if acc else 0
    
    to_date = datetime.now() + timedelta(days=1)
    from_date = datetime.now() - timedelta(days=days_back)
    
    deals = mt5.history_deals_get(from_date, to_date)
    if deals is None or len(deals) == 0: return None, None, None, "No se encontró historial."
    df_deals = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    
    # Buffer de órdenes para detectar SL/TP de órdenes pendientes antiguas
    from_date_orders = from_date - timedelta(days=180) 
    orders = mt5.history_orders_get(from_date_orders, to_date)
    
    df_orders = pd.DataFrame(list(orders), columns=orders[0]._asdict().keys()) if orders else pd.DataFrame()
    
    df_deposits = df_deals[df_deals['type'] == 2].copy()
    if not df_deposits.empty:
        df_deposits['time'] = pd.to_datetime(df_deposits['time'], unit='s')
        # MODIFICACIÓN: Renombrar explícitamente 'comment' a 'Nota' aquí
        df_deposits = df_deposits[['time', 'profit', 'comment']].rename(columns={'time':'Fecha', 'profit':'Monto', 'comment': 'Nota'})

    df_trades = df_deals[(df_deals['entry'].isin([0, 1])) & (df_deals['type'].isin([0, 1])) & (df_deals['symbol'].notna())].copy()
    if df_trades.empty: return pd.DataFrame(), df_deposits, current_bal, "Sin trades ejecutados."

    for c in ['commission', 'swap', 'fee']: 
        if c not in df_trades.columns: df_trades[c] = 0.0
        else: df_trades[c] = df_trades[c].fillna(0.0)

    trades = df_trades.groupby('position_id').agg({
        'symbol': 'first', 'time': ['first', 'last'], 'price': ['first', 'last'],
        'profit': 'sum', 'commission': 'sum', 'swap': 'sum', 'volume': 'first', 'type': 'first',
        'reason': 'last'
    })
    
    trades.columns = ['symbol', 'entrytime', 'exittime', 'entryprice', 'exitprice', 'gross_pnl', 'commission', 'swap', 'volume', 'type_op', 'exit_reason']
    trades = trades.reset_index()

    trades['netpnl'] = trades['gross_pnl'] + trades['commission'] + trades['swap']

    # === LÓGICA DE RECUPERACIÓN DE SL VERDADERO (MÁXIMO RIESGO) ===
    # Escaneamos órdenes y deals para encontrar el SL que estuvo MÁS LEJOS del precio de entrada (Riesgo Inicial)
    
    candidates = []
    
    # 1. Recolectar SLs de Órdenes Históricas (Blindado contra errores)
    if not df_orders.empty and 'position_id' in df_orders.columns and 'sl' in df_orders.columns:
        try:
            temp_o = df_orders[['position_id', 'sl']].copy()
            temp_o['sl'] = pd.to_numeric(temp_o['sl'], errors='coerce').fillna(0.0)
            temp_o = temp_o[temp_o['sl'] > 0]
            # Normalizamos ID a entero para evitar problemas de merge
            temp_o['position_id'] = temp_o['position_id'].astype('int64')
            candidates.append(temp_o)
        except Exception:
            pass # Si falla conversión, ignoramos este bloque
        
    # 2. Recolectar SLs de Deals Históricos (Blindado)
    if not df_deals.empty and 'position_id' in df_deals.columns and 'sl' in df_deals.columns:
        try:
            temp_d = df_deals[['position_id', 'sl']].copy()
            temp_d['sl'] = pd.to_numeric(temp_d['sl'], errors='coerce').fillna(0.0)
            temp_d = temp_d[temp_d['sl'] > 0]
            temp_d['position_id'] = temp_d['position_id'].astype('int64')
            candidates.append(temp_d)
        except Exception:
            pass

    if candidates:
        all_sl = pd.concat(candidates, ignore_index=True)
        
        # Preparamos subset de trades para cruzar
        trades_subset = trades[['position_id', 'entryprice']].copy()
        trades_subset['position_id'] = trades_subset['position_id'].astype('int64')
        
        # Cruzamos todos los SL encontrados con el precio de entrada de la posición
        merged_sl = all_sl.merge(trades_subset, on='position_id', how='left')
        
        # Filtramos filas donde no hubo cruce (huérfanos)
        merged_sl = merged_sl.dropna(subset=['entryprice'])
        
        if not merged_sl.empty:
            # Calculamos la distancia absoluta Entry - SL
            merged_sl['dist'] = (merged_sl['entryprice'] - merged_sl['sl']).abs()
            
            # Ordenamos: Primero por ID, luego por Distancia DESCENDENTE (el más lejano primero)
            merged_sl = merged_sl.sort_values(['position_id', 'dist'], ascending=[True, False])
            
            # Nos quedamos con el primero de cada grupo (el de mayor riesgo)
            best_sl = merged_sl.drop_duplicates('position_id')[['position_id', 'sl']]
            
            # Mapeamos de vuelta al dataframe principal
            sl_map = best_sl.set_index('position_id')['sl']
            
            # Convertimos ID de trades a int64 para asegurar el match
            trades['temp_id'] = trades['position_id'].astype('int64')
            trades['sl'] = trades['temp_id'].map(sl_map).fillna(0.0)
            trades.drop(columns=['temp_id'], inplace=True)
        else:
            trades['sl'] = 0.0
    else:
        trades['sl'] = 0.0
        
    # Último recurso: Si se cerró por SL (reason=2), usamos el precio de salida como SL
    sl_hit_mask = (trades['exit_reason'] == 2)
    trades['sl'] = np.where((trades['sl'] == 0) & sl_hit_mask, trades['exitprice'], trades['sl'])

    trades['entrytime'] = pd.to_datetime(trades['entrytime'], unit='s')
    trades['exittime'] = pd.to_datetime(trades['exittime'], unit='s')
    trades = trades.sort_values('entrytime')

    trades['day_name'] = trades['entrytime'].apply(get_day_name_es)
    trades['session'] = trades['entrytime'].apply(determine_session)
    trades['hour'] = trades['entrytime'].dt.hour # Nueva columna para el Heatmap

    trades['direction'] = trades['type_op'].apply(lambda x: 'Sell' if x == 1 else 'Buy')
    trades['dir_mult'] = trades['type_op'].apply(lambda x: -1 if x == 1 else 1)
    
    trades['risk_price'] = abs(trades['entryprice'] - trades['sl'])
    # Validamos SL solo si tiene sentido (>0)
    trades['valid_sl'] = (trades['sl'] > 0) & (trades['risk_price'] > 0)
    
    trades['r_multiple'] = trades.apply(lambda r: (r['dir_mult'] * (r['exitprice'] - r['entryprice'])) / r['risk_price'] if r['valid_sl'] else np.nan, axis=1)
    trades['risk_cash_est'] = trades.apply(lambda r: abs(r['gross_pnl'] / r['r_multiple']) if abs(r['r_multiple']) > 0.1 else np.nan, axis=1)
    
    physics = trades.apply(calculate_trade_physics, axis=1)
    physics.columns = ['mae', 'mfe', 'mae_r', 'mfe_r']
    trades = pd.concat([trades, physics], axis=1)
    
    start_cap = current_bal - trades['netpnl'].sum()
    trades['equity'] = start_cap + trades['netpnl'].cumsum()
    trades['equity_gross'] = start_cap + trades['gross_pnl'].cumsum() 
    trades['prev_equity'] = trades['equity'].shift(1).fillna(start_cap)
    
    return trades, df_deposits, start_cap, None

def calculate_stats(df, start_cap, df_deposits):
    if df is None or len(df) < 2: return None
    
    # ==============================================================================
    # 1⃣ DISOLUCIÓN ESTADÍSTICA DE RIESGO (LÓGICA HÍBRIDA PROGRESIVA)
    # ==============================================================================
    
    # A) SEPARACIÓN DE UNIVERSOS
    # Identificamos pérdidas en ambos mundos para estimar la "Unidad de Riesgo" ($)
    # Universo Real: Trades con SL explícito (valid_sl=True)
    losses_real = df[(df['valid_sl']) & (df['netpnl'] < 0)]
    risk_real_cash = abs(losses_real['netpnl'].mean()) if not losses_real.empty else 0
    
    # Universo Proxy: Trades sin SL (valid_sl=False)
    losses_proxy = df[(~df['valid_sl']) & (df['netpnl'] < 0)]
    risk_proxy_cash = abs(losses_proxy['netpnl'].mean()) if not losses_proxy.empty else 0
    
    # Fallback de Seguridad: Si falta data en algún universo, usamos el otro o 1%
    if risk_real_cash == 0: 
        risk_real_cash = risk_proxy_cash if risk_proxy_cash > 0 else start_cap * 0.01
    if risk_proxy_cash == 0:
        risk_proxy_cash = risk_real_cash

    # B) CÁLCULO DEL PESO DINÁMICO (W_PROXY)
    # El peso del proxy decae exponencialmente conforme aumentan los trades con SL válido
    n_valid_sl = df['valid_sl'].sum()
    
    W_MIN = 0.15      # Límite inferior: El proxy histórico nunca desaparece del todo (data es data)
    DECAY_K = 20.0    # Constante de tiempo: Controla qué tan rápido "confiamos" en el riesgo real
    
    # w_proxy empieza en 1.0 (si n=0) y baja suavemente hasta W_MIN
    w_proxy = max(W_MIN, np.exp(-n_valid_sl / DECAY_K))
    
    # C) RIESGO EFECTIVO PONDERADO ($)
    # Este es el valor "blend" que usaremos para normalizar los trades antiguos
    effective_risk_cash = (w_proxy * risk_proxy_cash) + ((1 - w_proxy) * risk_real_cash)

    # D) CÁLCULO DE R-MULTIPLE FINAL
    def calculate_blended_r(row):
        # 1. Trades con SL Real (Ex-Ante): Usamos el cálculo geométrico original
        if row['valid_sl'] and pd.notna(row['r_multiple']) and abs(row['r_multiple']) != np.inf:
            return row['r_multiple']
        else:
            # 2. Trades Proxy (Sin SL): Normalizamos por el Riesgo Efectivo Disuelto
            # Esto actualiza el pasado basándose en la conducta de riesgo presente
            return row['netpnl'] / effective_risk_cash

    df['r_multiple'] = df.apply(calculate_blended_r, axis=1)
    
    # ==============================================================================
    # 2⃣ SERIES TEMPORALES & EQUITY (HISTÓRICO)
    # ==============================================================================
    daily = df.set_index('entrytime').resample('D')['netpnl'].sum().fillna(0).to_frame('pnl')
    daily['equity'] = start_cap + daily['pnl'].cumsum()
    daily['prev_equity'] = daily['equity'].shift(1).fillna(start_cap)
    daily['ret'] = np.log(daily['equity'] / daily['prev_equity'].replace(0, np.nan)).fillna(0)
    daily['peak'] = daily['equity'].cummax()
    daily['dd'] = (daily['equity'] - daily['peak']) / daily['peak']

    # ==============================================================================
    # 3⃣ MÉTRICAS PROBABILÍSTICAS (ROBUSTAS)
    # ==============================================================================
    valid_r = df['r_multiple'].replace([np.inf, -np.inf], np.nan).dropna().values
    
    # Momentos de la distribución R
    mu_r = np.mean(valid_r)
    sigma_r = np.std(valid_r, ddof=1)
    
    time_span_days = max((df['entrytime'].max() - df['entrytime'].min()).days, 1)
    trades_per_year = len(df) * (365 / time_span_days)

    # Sharpe & Sortino (Probabilísticos)
    robust_sharpe = (mu_r / sigma_r) * np.sqrt(trades_per_year) if sigma_r > 0 else 0
    
    downside_r = valid_r[valid_r < 0]
    downside_dev = np.sqrt(np.mean(downside_r**2)) if len(downside_r) > 0 else 1e-6
    final_sortino = (mu_r / downside_dev) * np.sqrt(trades_per_year)

    # SQN
    sqn = np.sqrt(len(df)) * (mu_r / sigma_r) if sigma_r > 0 else 0

    # ==============================================================================
    # 4⃣ GESTIÓN DE RIESGO
    # ==============================================================================
    total_net = df['netpnl'].sum()
    
    # Riesgo Promedio (%) para proyecciones
    # Usamos el Riesgo Efectivo ($) normalizado al capital inicial como base consistente
    avg_risk_pct = effective_risk_cash / start_cap
    
    # Peor pérdida histórica como % (Max Risk)
    max_risk_pct = abs(df['netpnl'].min()) / start_cap

    # VaR y CVaR (Basados en distribución R empírica escalada por Riesgo Efectivo)
    var_95_r = np.percentile(valid_r, 5)
    cvar_95_r = np.mean(valid_r[valid_r <= var_95_r])
    var_95_pct = abs(var_95_r * avg_risk_pct)
    cvar_95_pct = abs(cvar_95_r * avg_risk_pct)

    # Volatilidad
    std_daily = daily['ret'].std()
    vol_ann = std_daily * np.sqrt(252)
    ulcer = np.sqrt(np.mean(daily['dd']**2))
    
    skew_val = skew(daily['ret'])
    kurt_val = kurtosis(daily['ret'])

    # Kelly Empírico (Mean / Mean_Square)
    mean_r2 = np.mean(valid_r**2)
    raw_kelly = mu_r / mean_r2 if mean_r2 > 0 else 0
    kelly_conservative = min(max(raw_kelly * 0.5, 0.0), 0.25)

    # Métricas Nominales
    wins = df[df['netpnl'] > 0]
    losses = df[df['netpnl'] <= 0]
    win_rate = len(wins) / len(df)
    
    avg_w = wins['netpnl'].mean() if not wins.empty else 0
    avg_l = abs(losses['netpnl'].mean()) if not losses.empty else 1
    payoff = avg_w / avg_l
    pf = wins['netpnl'].sum() / abs(losses['netpnl'].sum()) if losses['netpnl'].sum() != 0 else 999

    # CAGR & Calmar
    final_equity = daily['equity'].iloc[-1]
    years = max(time_span_days / 365, 0.01)
    cagr_geo = (final_equity / start_cap) ** (1 / years) - 1 if start_cap > 0 and final_equity > 0 else 0
    max_dd_hist = abs(daily['dd'].min())
    calmar = cagr_geo / max_dd_hist if max_dd_hist > 0 else 0

    # ==============================================================================
    # 5⃣ SIMULACIÓN MONTECARLO (CONSISTENTE)
    # ==============================================================================
    n_sims = 200
    n_trades_sim = len(df)
    
    # Bootstrap sobre R-Multiples (que ahora mezcla Real y Proxy ajustado)
    sim_r = np.random.choice(valid_r, size=(n_sims, n_trades_sim), replace=True)
    
    # Proyección usando el Riesgo Efectivo como unidad base
    sim_pnl = sim_r * effective_risk_cash 
    sim_curves = np.cumsum(sim_pnl, axis=1) + daily['equity'].iloc[-1]
    
    ruin_threshold = start_cap * 0.5
    prob_ruin = np.sum(np.min(sim_curves, axis=1) < ruin_threshold) / n_sims

    # Rolling Metrics
    df['roll_expectancy'] = df['r_multiple'].rolling(20).mean()
    df['roll_volatility'] = df['netpnl'].rolling(20).std()

    return {
        "basic": { "sqn": sqn, "expectancy_r": mu_r, "sharpe": robust_sharpe, "net_profit": total_net },
        "perf": { "cagr": cagr_geo, "pf": pf, "calmar": calmar, "sortino": final_sortino, "win_rate": win_rate, "payoff": payoff },
        "risk": { "avg_risk": avg_risk_pct, "max_risk": max_risk_pct, "vol_ann": vol_ann, "var": var_95_pct, "cvar": cvar_95_pct, "kelly": kelly_conservative, "skew": skew_val, "kurt": kurt_val },
        "stress": { "ulcer": ulcer, "max_dd": max_dd_hist, "ruin": prob_ruin },
        "costs": { 
            "comm": df['commission'].sum(), "swap": df['swap'].sum(), "gross": df['gross_pnl'].sum(), "net": total_net,
            "drag": abs((df['commission'].sum() + df['swap'].sum()) / df['gross_pnl'].sum()) if df['gross_pnl'].sum() != 0 else 0
        },
        "mc": sim_curves, "ts": daily, "df": df
    }

#==============================================================================
# FUNCIONES AUXILIARES NUEVAS (LIVE DATA & EXPORT)
#==============================================================================
def get_live_positions_data():
    """Obtiene posiciones abiertas y calcula riesgo vivo"""
    if not mt5.initialize(): return None
    positions = mt5.positions_get()
    if positions is None or len(positions) == 0:
        return pd.DataFrame()
    
    df_live = pd.DataFrame(list(positions), columns=positions[0]._asdict().keys())
    
    # Enriquecer data viva
    df_live['type_str'] = df_live['type'].apply(lambda x: 'Buy' if x == 0 else 'Sell')
    # Distancia al SL (Distancia a Ruina del trade individual)
    df_live['dist_sl_price'] = df_live.apply(lambda r: abs(r['price_current'] - r['sl']) if r['sl'] > 0 else np.nan, axis=1)
    
    return df_live

def convert_df_to_csv(df):
    """Convierte dataframe a CSV para descarga"""
    return df.to_csv(index=False).encode('utf-8')

#==============================================================================
# COMPONENTES UI (EXISTENTE)
#==============================================================================
def value_box(value, subtitle, icon, color="bg-blue"):
    st.markdown(f"""
        <div class="small-box {color}">
            <div class="inner">
                <h3>{value}</h3>
                <p>{subtitle}</p>
            </div>
            <div class="icon"><i class="fas fa-{icon}"></i></div>
        </div>
    """, unsafe_allow_html=True)

def info_box(text, number, icon, color="bg-aqua"):
    st.markdown(f"""
        <div class="info-box">
            <span class="info-box-icon {color}"><i class="fas fa-{icon}"></i></span>
            <div class="info-box-content">
                <span class="info-box-text">{text}</span>
                <span class="info-box-number">{number}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

def box_header(title, status="box-primary"):
    st.markdown(f"""<div class="box {status}"><div class="box-header">{title}</div></div>""", unsafe_allow_html=True)

#==============================================================================
# APP LAYOUT
#==============================================================================
st.markdown('<link rel="stylesheet" href="https://use.fontawesome.com/releases/v5.15.4/css/all.css">', unsafe_allow_html=True)

with st.sidebar:
    st.markdown('<span class="main-header">Micro-Fund Audit Tool</span>', unsafe_allow_html=True)
    st.markdown('<span class="sub-header">Institutional Analytics</span>', unsafe_allow_html=True)
    
    # 3. Menú CON CALLBACK (La solución del bug)
    menu = st.radio(
        "Navegación", 
        ["Resumen Ejecutivo", "Monitor en Vivo (Riesgo)", "Análisis de Costos", "Análisis de Riesgo", "Robustez Temporal", "Eficiencia Operativa", "Data Journal", "Journal Visual"], 
        index=0, 
        key="main_nav",
        on_change=on_menu_change,
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    st.markdown('<span class="sub-header"> WATCHDOG SETTINGS</span>', unsafe_allow_html=True)
    # MODIFICACIÓN 1: Límite de pérdida diaria establecido en 10 dólares
    daily_loss_limit = st.number_input("Límite Pérdida Diaria ($)", value=10.0, step=1.0)
    
    st.markdown("---")
    days = st.number_input("Días de Análisis", min_value=30, value=365)
    if st.button(" Sincronizar MT5", type="primary"):
        with st.spinner("Conectando..."):
            df_raw, df_deps, cap, err = get_mt5_data(days)
            if err: st.error(err)
            else:
                st.session_state.data = df_raw; st.session_state.cap = cap; st.session_state.deps = df_deps
                st.session_state.stats = calculate_stats(df_raw, cap, df_deps)
                st.rerun()

# CONTENEDOR MAESTRO (SINGLE CONTAINER PATTERN)
#Todo el contenido visual se renderiza AQUÍ adentro. Al cambiar de pestaña,
#Streamlit destruye y reconstruye este contenedor, eliminando residuos visuales.
main_placeholder = st.empty()

with main_placeholder.container():
    # MODIFICACIÓN DE SEGURIDAD PARA EVITAR CRASH
    if 'data' in st.session_state and st.session_state.stats is not None:
        m = st.session_state.stats
        df = m['df']
        
        # ==============================================================================
        #  WATCHDOG LOGIC (GLOBAL)
        # ==============================================================================
        live_positions_wd = get_live_positions_data()
        floating_pnl_wd = live_positions_wd['profit'].sum() + live_positions_wd['swap'].sum() if not live_positions_wd.empty else 0.0
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_closed_pnl = df[df['entrytime'] >= today_start]['netpnl'].sum()
        total_day_pnl = today_closed_pnl + floating_pnl_wd
        
        if daily_loss_limit > 0 and total_day_pnl <= -(daily_loss_limit * 0.9):
            pct_limit = abs(total_day_pnl / daily_loss_limit) * 100
            st.markdown(f"""
            <div style="background-color: #7F1D1D; color: #FECACA; padding: 20px; border-radius: 10px; border: 2px solid #EF4444; margin-bottom: 20px; text-align: center;">
                <h2 style="color: #FECACA; margin:0;"><i class="fas fa-exclamation-triangle"></i> WATCHDOG ALERT TRIGGERED</h2>
                <p style="font-size: 18px; font-weight: bold; margin-top: 10px;">
                    PÉRDIDA DEL DÍA: ${total_day_pnl:,.2f} ({pct_limit:.1f}% del Límite)
                </p>
                <p style="margin: 0;"> DETENER OPERATIVA INMEDIATAMENTE. LÍMITE: ${daily_loss_limit}</p>
            </div>
            """, unsafe_allow_html=True)
        
        # ==============================================================================
        #  PÁGINAS (DENTRO DEL CONTENEDOR MAESTRO)
        # ==============================================================================
        
        if menu == "Resumen Ejecutivo":
            c1, c2, c3, c4 = st.columns(4)
            with c1: 
                col_sqn = "bg-green" if m['basic']['sqn'] > 2 else "bg-yellow"
                value_box(f"{m['basic']['sqn']:.2f}", "System Quality (SQN)", "microchip", col_sqn)
            with c2: 
                exp_val = f"{m['basic']['expectancy_r']:.2f} R" if m['basic']['expectancy_r'] < 100 else f"${m['basic']['expectancy_r']:.2f}"
                value_box(exp_val, "Esperanza (R)", "balance-scale", "bg-purple")
            with c3: 
                col_sh = "bg-green" if m['basic']['sharpe'] > 1 else "bg-red"
                value_box(f"{m['basic']['sharpe']:.2f}", "Sharpe Ratio", "chart-area", col_sh)
            with c4: 
                col_net = "bg-green" if m['basic']['net_profit'] > 0 else "bg-red"
                value_box(f"${m['basic']['net_profit']:,.0f}", "Net Profit", "wallet", col_net)
            
            c_eq, c_dist = st.columns([2, 1])
            with c_eq:
                box_header("Curva de Equity: Bruta vs Neta", "box-primary")
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df['entrytime'], y=df['equity_gross'], name="Equity Bruta", line=dict(color='#718096', dash='dot')))
                fig.add_trace(go.Scatter(x=df['entrytime'], y=df['equity'], name="Equity Neta", line=dict(color='#3B82F6', width=3)))
                fig.update_layout(template="plotly_dark", height=450, margin=dict(t=20, b=20), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)
            with c_dist:
                box_header("Distribución de Retornos (R)", "box-primary")
                fig = px.histogram(df, x="r_multiple", nbins=30, color_discrete_sequence=['#8B5CF6'])
                fig.update_layout(template="plotly_dark", height=450, margin=dict(t=20, b=20), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)
                
            box_header("Historia de Retornos (PnL Neto)", "box-primary")
            start_date = df['entrytime'].min().normalize()
            end_date = df['entrytime'].max().normalize()
            all_dates = pd.date_range(start=start_date, end=end_date, freq='D')
            daily_pnl = df.set_index('entrytime').resample('D')['netpnl'].sum().reindex(all_dates, fill_value=0).reset_index()
            daily_pnl.columns = ['entrytime', 'netpnl']
            fig_bar = px.bar(
                daily_pnl, x='entrytime', y='netpnl', 
                color=daily_pnl['netpnl'] > 0, 
                color_discrete_map={True:'#10B981', False:'#EF4444'}
            )
            fig_bar.update_layout(
                template="plotly_dark", height=300, showlegend=False, 
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(title="", range=[start_date, end_date]), yaxis_title="PnL ($)"
            )
            st.plotly_chart(fig_bar, use_container_width=True)
            
            box_header("Performance Matrix", "box-primary")
            kpi_df = pd.DataFrame({
                "Métrica": ["CAGR", "Profit Factor", "Calmar", "Sortino", "Win Rate", "Payoff"],
                "Valor": [f"{m['perf']['cagr']:.1%}", f"{m['perf']['pf']:.2f}", f"{m['perf']['calmar']:.2f}", 
                          f"{m['perf']['sortino']:.2f}", f"{m['perf']['win_rate']:.1%}", f"{m['perf']['payoff']:.2f}"]
            })
            st.dataframe(kpi_df, use_container_width=True, hide_index=True)

        # ==============================================================================
        #  MONITOR EN VIVO (CON AUTO-ARRANQUE)
        # ==============================================================================
        elif menu == "Monitor en Vivo (Riesgo)":
            
            # Revisamos si estamos en fase de arranque (definida por el callback)
            is_starting = st.session_state.get('live_starting_up', False)

            col_ref, col_head = st.columns([1, 4])
            with col_ref:
                # key='toggle_live' mantiene el estado. El callback asegura que arranque en False.
                active_refresh = st.toggle(" Live Update", key="toggle_live")
                
            with col_head:
                box_header("Monitor de Riesgo Vivo (Live Exposure)", "box-danger")
                
            # Usamos la data live que ya obtuvimos para el Watchdog
            df_live = live_positions_wd
            
            if df_live.empty:
                st.info("No hay posiciones abiertas actualmente.")
            else:
                live_floating = df_live['profit'].sum() + df_live['swap'].sum()
                live_vol = df_live['volume'].sum()
                live_trades = len(df_live)
                
                c_l1, c_l2, c_l3 = st.columns(3)
                with c_l1:
                    col_float = "bg-green" if live_floating >= 0 else "bg-red"
                    value_box(f"${live_floating:,.2f}", "Floating PnL Total", "chart-line", col_float)
                with c_l2:
                    value_box(f"{live_vol:.2f}", "Volumen Expuesto (Lotes)", "layer-group", "bg-blue")
                with c_l3:
                    value_box(f"{live_trades}", "Trades Abiertos", "tags", "bg-purple")
                
                c_tbl, c_exp = st.columns([2, 1])
                with c_tbl:
                    box_header("Detalle de Posiciones", "box-primary")
                    view_live = df_live[['symbol', 'type_str', 'volume', 'price_open', 'price_current', 'sl', 'tp', 'profit', 'swap', 'dist_sl_price']].copy()
                    view_live.columns = ['Symbol', 'Type', 'Vol', 'Open', 'Current', 'SL', 'TP', 'Profit', 'Swap', 'Distancia Ruina']
                    def color_float(val):
                        color = '#10B981' if val > 0 else '#EF4444'
                        return f'color: {color}; font-weight: bold;'
                    st.dataframe(view_live.style.map(color_float, subset=['Profit']).format({
                        "Vol": "{:.2f}", "Open": "{:.5f}", "Current": "{:.5f}", 
                        "SL": "{:.5f}", "TP": "{:.5f}", "Profit": "${:.2f}", "Distancia Ruina": "{:.5f}"
                    }), use_container_width=True, hide_index=True)
                
                with c_exp:
                    box_header("Exposición por Divisa", "box-warning")
                    df_live['net_vol'] = df_live.apply(lambda r: r['volume'] if r['type'] == 0 else -r['volume'], axis=1)
                    exposure = df_live.groupby('symbol')[['net_vol', 'profit']].sum().reset_index()
                    st.dataframe(exposure.style.map(color_float, subset=['profit']).format({"net_vol": "{:.2f}", "profit": "${:.2f}"}), use_container_width=True, hide_index=True)
                    df_live['abs_vol'] = df_live['volume']
                    fig_exp = px.pie(df_live, values='abs_vol', names='symbol', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig_exp.update_layout(template="plotly_dark", height=300, margin=dict(t=0, b=0), showlegend=False)
                    fig_exp.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig_exp, use_container_width=True)

            # LÓGICA DE LOOP AL FINAL DEL BLOQUE (POST-RENDER)
            # Esto evita que se ejecute antes de dibujar la página
            if is_starting:
                time.sleep(1) # Esperamos 1s para que el usuario vea la tabla estática
                st.session_state.live_starting_up = False 
                st.session_state.force_toggle_on = True # Ordenamos encender en la sgte recarga
                st.rerun() # Recargamos
            elif active_refresh:
                time.sleep(2) # Loop normal de 2s
                st.rerun()

        elif menu == "Análisis de Costos":
            c1, c2, c3 = st.columns(3)
            with c1: info_box("Comisiones", f"${m['costs']['comm']:.2f}", "receipt", "bg-red")
            with c2: info_box("Swaps", f"${m['costs']['swap']:.2f}", "exchange-alt", "bg-yellow")
            with c3: info_box("Costo / Gross", f"{m['costs']['drag']:.1%}", "percent", "bg-blue")
            
            c_plot, c_tbl = st.columns([2, 1])
            with c_plot:
                box_header("Impacto Acumulado", "box-warning")
                df['cum_gross'] = df['gross_pnl'].cumsum()
                df['cum_costs'] = (df['commission'] + df['swap']).abs().cumsum()
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df['entrytime'], y=df['cum_gross'], name="Profit Bruto", line=dict(color='#10B981')))
                fig.add_trace(go.Scatter(x=df['entrytime'], y=df['cum_costs'], name="Costos", fill='tozeroy', line=dict(color='#EF4444')))
                fig.update_layout(template="plotly_dark", height=450, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=20, b=20))
                st.plotly_chart(fig, use_container_width=True)
            with c_tbl:
                box_header("Estructura de Costos", "box-warning")
                st.table(pd.DataFrame({
                    "Concepto": ["Comisiones", "Swaps", "Total Costos", "Profit Neto"],
                    "Valor": [f"${m['costs']['comm']:.2f}", f"${m['costs']['swap']:.2f}", 
                              f"${(m['costs']['comm']+m['costs']['swap']):.2f}", f"${m['costs']['net']:.2f}"]
                }))

        elif menu == "Análisis de Riesgo":
            box_header("Métricas Institucionales de Riesgo (Advanced)", "box-danger")
            risk_df = pd.DataFrame({
                "Métrica": ["Riesgo Medio %", "Riesgo Máx %", "Volatilidad Anual", "VaR 95%", "CVaR", "Kelly", "Skewness", "Kurtosis"],
                "Valor": [f"{m['risk']['avg_risk']:.2%}", f"{m['risk']['max_risk']:.2%}", f"{m['risk']['vol_ann']:.1%}", 
                          f"{m['risk']['var']:.2%}", f"{m['risk']['cvar']:.2%}", f"{m['risk']['kelly']:.2%}", 
                          f"{m['risk']['skew']:.2f}", f"{m['risk']['kurt']:.2f}"]
            })
            st.dataframe(risk_df.T, use_container_width=True, hide_index=True)
            
            # --- NUEVA SECCIÓN DE MONTECARLO INTERACTIVO ---
            st.markdown("---")
            box_header(" Simulador de Estrés (Montecarlo Interactivo)", "box-warning")
            
            # Controles
            col_ctrl_1, col_ctrl_2 = st.columns(2)
            with col_ctrl_1:
                # MODIFICADO: Ahora controlamos por % de Riesgo, estandarizando todos los activos
                mc_risk_pct = st.slider("Riesgo por Trade (% Cuenta)", 0.05, 5.0, 0.25, step=0.05, 
                                      help="Define qué % de tu capital actual arriesgarás en cada operación futura (Fixed Fractional Risk). Esto estandariza el riesgo entre activos (XAUUSD vs FX).")
            with col_ctrl_2:
                mc_horizon = st.number_input("Horizonte de Trades (Proyección)", 50, 5000, 200, help="Número de operaciones futuras a simular.")
            
            # Lógica de Simulación
            returns_pool = df['r_multiple'].replace([np.inf, -np.inf], np.nan).dropna().values
            
            # 1. Obtenemos el Equity Actual REAL
            current_equity = df['equity'].iloc[-1]
            
            # 2. Calculamos la Unidad de Riesgo ($) basada en el % seleccionado
            # Ejemplo: Si tienes $10,000 y eliges 1%, tu unidad de riesgo base es $100.
            # Independientemente de si operas Oro o Euro, asumimos que ajustas el lotaje para arriesgar $100.
            risk_unit_cash = current_equity * (mc_risk_pct / 100)
            
            if len(returns_pool) > 5:
                n_sims = 200 # Mantenemos ligero para rendimiento en vivo
                sim_r = np.random.choice(returns_pool, size=(n_sims, mc_horizon), replace=True)
                
                # 3. Proyección PnL = R-Multiple * Unidad de Riesgo ($)
                # Esto es puro y agnóstico al activo.
                sim_pnl = sim_r * risk_unit_cash
                
                equity_curves = np.zeros((n_sims, mc_horizon + 1))
                equity_curves[:, 0] = current_equity
                equity_curves[:, 1:] = current_equity + np.cumsum(sim_pnl, axis=1)
                
                # Métricas de Ruina
                ruin_threshold = st.session_state.cap * 0.5
                prob_ruin = np.mean(np.min(equity_curves, axis=1) < ruin_threshold) * 100
                
                # Gráfico
                fig_mc = go.Figure()
                x_axis = np.arange(mc_horizon + 1)
                
                # Trazas de simulación (transparencia alta)
                for i in range(min(n_sims, 50)): # Solo dibujamos 50 para no saturar
                    fig_mc.add_trace(go.Scatter(x=x_axis, y=equity_curves[i, :], mode='lines',
                                            line=dict(width=1, color='rgba(96, 165, 250, 0.1)'), showlegend=False, hoverinfo='skip'))
                
                # Mediana
                median_curve = np.median(equity_curves, axis=0)
                fig_mc.add_trace(go.Scatter(x=x_axis, y=median_curve, mode='lines',
                                        line=dict(width=3, color='#3B82F6'), name='Escenario Probable (Mediana)'))
                
                # Peor caso (P5)
                p5_curve = np.percentile(equity_curves, 5, axis=0)
                fig_mc.add_trace(go.Scatter(x=x_axis, y=p5_curve, mode='lines',
                                        line=dict(width=2, color='#EF4444', dash='dot'), name='Escenario de Estrés (5% Peor)'))
                
                # Línea de Ruina
                fig_mc.add_shape(type="line", x0=0, y0=ruin_threshold, x1=mc_horizon, y1=ruin_threshold,
                              line=dict(color="#EF4444", width=2, dash="dash"))
                
                fig_mc.update_layout(
                    template="plotly_dark", height=450, 
                    title=f"Proyección con Riesgo Fijo del {mc_risk_pct}%",
                    yaxis_title="Balance ($)", xaxis_title="Número de Trades Futuros",
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    margin=dict(t=40, b=20)
                )
                
                st.plotly_chart(fig_mc, use_container_width=True)
                
                # Alertas de Riesgo
                if prob_ruin > 5.0:
                    st.error(f" ALERTA DE RIESGO: Arriesgando un {mc_risk_pct}% por trade, tu probabilidad de quebrar la cuenta (>50% DD) es del {prob_ruin:.1f}%.")
                else:
                    st.success(f" ANÁLISIS DE ESTRÉS: Arriesgando un {mc_risk_pct}%, tu sistema es estable (Prob. Ruina: {prob_ruin:.1f}%).")
            else:
                st.warning("Se necesitan al menos 5 trades cerrados para correr la simulación.")

            # --- ANTIGUO BLOQUE (UNDERWATER) ---
            box_header("Underwater Plot (Histórico Real)", "box-danger")
            fig_uw = go.Figure(go.Scatter(x=m['ts'].index, y=m['ts']['dd']*100, fill='tozeroy', line=dict(color='#EF4444')))
            fig_uw.update_layout(template="plotly_dark", height=350, yaxis_title="Drawdown %", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_uw, use_container_width=True)

        elif menu == "Robustez Temporal":
            c1, c2 = st.columns(2)
            with c1:
                box_header("Rolling Expectancy (20 Trades)", "box-primary")
                roll_exp = df['roll_expectancy'].dropna()
                fig = px.line(x=df.loc[roll_exp.index, 'entrytime'], y=roll_exp, color_discrete_sequence=['#8B5CF6'])
                fig.add_hline(y=0, line_dash="dash", line_color="#EF4444")
                fig.update_layout(template="plotly_dark", height=450, yaxis_title="Expectancy (R)", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                box_header("Rolling Volatility (20 Trades)", "box-primary")
                roll_vol = df['roll_volatility'].dropna()
                fig = px.line(x=df.loc[roll_vol.index, 'entrytime'], y=roll_vol, color_discrete_sequence=['#F59E0B'])
                fig.update_layout(template="plotly_dark", height=450, yaxis_title="Volatilidad ($)", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)
                
            st.markdown("---")
            c_hm_head, c_hm_exp = st.columns([3, 1])
            with c_hm_head:
                box_header("Rendimiento Mensual (Monthly Analytics)", "box-primary")
            
            df_hm = df.copy()
            df_hm['year'] = df_hm['entrytime'].dt.year
            df_hm['month'] = df_hm['entrytime'].dt.month
            month_map = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun', 
                         7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
            df_hm['month_name'] = df_hm['month'].map(month_map)
            df_hm = df_hm.sort_values('entrytime')
            df_hm['prev_bal'] = df_hm['equity'] - df_hm['netpnl']
            hm_data = df_hm.groupby(['year', 'month', 'month_name']).agg({
                'netpnl': 'sum',
                'prev_bal': 'first'
            }).reset_index()
            hm_data['ret_pct'] = hm_data.apply(lambda row: (row['netpnl'] / row['prev_bal']) * 100 if row['prev_bal'] > 0 else 0, axis=1)

            current_min_year = int(df_hm['year'].min()) if not df_hm.empty else datetime.now().year
            all_years_options = list(range(2030, current_min_year - 1, -1))
            years_in_data = sorted(df_hm['year'].unique().tolist(), reverse=True)
            col_y_sel, _ = st.columns([1, 3])
            with col_y_sel:
                selected_years = st.multiselect(" Seleccionar Años", all_years_options, default=years_in_data)
            
            if selected_years:
                hm_data_filtered = hm_data[hm_data['year'].isin(selected_years)]
                hm_pivot = pd.DataFrame()
                if not hm_data_filtered.empty:
                    hm_pivot = hm_data_filtered.pivot(index='year', columns='month_name', values='ret_pct')
                for y in selected_years:
                    if y not in hm_pivot.index:
                        hm_pivot.loc[y] = np.nan
                hm_pivot = hm_pivot.reindex(selected_years)
                months_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                hm_pivot = hm_pivot.reindex(columns=months_order)
                
                with c_hm_exp:
                    csv_hm = convert_df_to_csv(hm_pivot)
                    st.download_button(label=" Exportar Heatmap", data=csv_hm, file_name='heatmap_returns.csv', mime='text/csv')
                
                z_values = hm_pivot.values
                x_values = months_order
                y_values = hm_pivot.index.tolist()
                text_values = []
                for row in z_values:
                    row_txt = []
                    for val in row:
                        if pd.isna(val): row_txt.append("")
                        else: row_txt.append(f"{val:+.2f}%")
                    text_values.append(row_txt)
                max_abs = np.nanmax(np.abs(z_values)) if not np.all(np.isnan(z_values)) else 1
                
                fig_hm = go.Figure(data=go.Heatmap(
                    z=z_values, x=x_values, y=y_values, text=text_values, texttemplate="%{text}",
                    textfont={"size": 13, "family": "Inter", "color": "white"}, hoverinfo='none',
                    colorscale=[[0.0, "rgba(220, 38, 38, 0.7)"], [0.5, "rgba(30, 41, 59, 0.0)"], [1.0, "rgba(5, 150, 105, 0.7)"]],
                    zmid=0, zmin=-max_abs, zmax=max_abs, showscale=False, xgap=4, ygap=4
                ))
                fig_hm.update_layout(
                    template="plotly_dark", height=max(250, len(y_values) * 55), margin=dict(t=40, b=20, l=0, r=0),
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    xaxis=dict(side="top", showgrid=False, zeroline=False, tickfont=dict(size=14, color="#94A3B8")),
                    yaxis=dict(showgrid=False, zeroline=False, type='category', tickfont=dict(size=14, color="#E2E8F0", weight="bold"))
                )
                st.plotly_chart(fig_hm, use_container_width=True)
            else:
                st.info("Selecciona al menos un año para visualizar la tabla.")

        elif menu == "Eficiencia Operativa":
            st.markdown("### Configuración de Análisis")
            col_sel, col_empty = st.columns([1, 3])
            with col_sel:
                selected_symbol = st.selectbox("Seleccionar Activo", ["Global"] + list(df['symbol'].unique()))
            
            df_eff = df.copy()
            if selected_symbol != "Global":
                df_eff = df_eff[df_eff['symbol'] == selected_symbol]
            
            # MODIFICACIÓN 3: Cálculo Dinámico del Factor de Ganancia (Payoff Ratio)
            wins_eff = df_eff[df_eff['netpnl'] > 0]
            losses_eff = df_eff[df_eff['netpnl'] <= 0]
            
            avg_win_eff = wins_eff['netpnl'].mean() if not wins_eff.empty else 0
            avg_loss_eff = abs(losses_eff['netpnl'].mean()) if not losses_eff.empty else 0.0001 # Evitar div por cero
            payoff_ratio_eff = avg_win_eff / avg_loss_eff
            
            st.metric("Factor de Ganancia Promedio (Avg Win / Avg Loss)", f"{payoff_ratio_eff:.2f}", delta=f"{len(df_eff)} Trades")
            
            winning_trades = df_eff[df_eff['netpnl'] > 0]
            if not winning_trades.empty:
                opt_sl_dist = abs(winning_trades['mae'].quantile(0.05)) 
                opt_tp_dist = winning_trades['mfe'].median()
                
                if selected_symbol != "Global":
                    st.markdown(f"####  Optimización para {selected_symbol}")
                    c_opt1, c_opt2 = st.columns(2)
                    with c_opt1:
                        value_box(f"{opt_sl_dist:.5f}", "SL Sugerido (95% Winners)", "shield-alt", "bg-red")
                        st.caption(f"El 95% de tus trades ganadores no tuvieron un drawdown mayor a {opt_sl_dist:.5f} antes de ir a profit.")
                    with c_opt2:
                        value_box(f"{opt_tp_dist:.5f}", "TP Potencial (Mediana MFE)", "crosshairs", "bg-green")
                        st.caption(f"La mitad de tus trades ganadores alcanzaron al menos {opt_tp_dist:.5f} de recorrido a favor.")

            c1, c2 = st.columns(2)
            with c1:
                box_header(f"Eficiencia Entrada (MAE) - {selected_symbol}", "box-primary")
                fig = px.scatter(df_eff, x='mae_r', y='r_multiple', color=df_eff['netpnl']>0, 
                                 color_discrete_map={True:'#10B981', False:'#EF4444'},
                                 hover_data=['mae', 'r_multiple', 'netpnl'])
                fig.add_vline(x=-1, line_dash="dash", line_color="white", annotation_text="SL Teórico")
                fig.update_layout(template="plotly_dark", height=500, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                 xaxis_title="MAE [R]", yaxis_title="Retorno [R]")
                st.plotly_chart(fig, use_container_width=True)
            
            with c2:
                box_header(f"Eficiencia Salida (MFE) - {selected_symbol}", "box-primary")
                fig = px.scatter(df_eff, x='mfe_r', y='r_multiple', color=df_eff['netpnl']>0, 
                                 color_discrete_map={True:'#10B981', False:'#EF4444'},
                                 hover_data=['mfe', 'r_multiple', 'netpnl'])
                fig.add_shape(type="line", x0=0, y0=0, x1=df_eff['mfe_r'].max(), y1=df_eff['mfe_r'].max(), line=dict(dash="dot", color="#6B7280"))
                fig.update_layout(template="plotly_dark", height=500, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                 xaxis_title="MFE [R]", yaxis_title="Retorno [R]")
                st.plotly_chart(fig, use_container_width=True)
            
            # --- Análisis de Duración ---
            st.markdown("---")
            box_header(f"Análisis de Duración (Time Held) - {selected_symbol}", "box-warning")
            
            # Calcular duración en minutos
            df_eff['duration_mins'] = (df_eff['exittime'] - df_eff['entrytime']).dt.total_seconds() / 60
            
            # Crear Scatter Plot: Duración vs Resultado
            fig_dur = px.scatter(
                df_eff, 
                x='duration_mins', 
                y='netpnl', 
                color=df_eff['netpnl']>0,
                color_discrete_map={True:'#10B981', False:'#EF4444'},
                hover_data=['entrytime', 'duration_mins', 'netpnl'],
                labels={'duration_mins': 'Duración (Minutos)', 'netpnl': 'PnL ($)'}
            )
            
            # Añadir línea de promedio de ganancia/pérdida
            fig_dur.add_hline(y=0, line_dash="dash", line_color="white")
            
            fig_dur.update_layout(
                template="plotly_dark",
                height=450,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                showlegend=False,
                xaxis_title="Duración del Trade (Minutos)",
                yaxis_title="Resultado Neto ($)"
            )
            st.plotly_chart(fig_dur, use_container_width=True)

            # --- ZONA DE MUERTE (DEATH ZONE HEATMAP) - MOVIDO AL FINAL Y REDISEÑADO ---
            st.markdown("---")
            box_header(" Death Zone Analysis (Heatmap Hora vs Día)", "box-danger")
            st.caption("Patrones temporales de rendimiento. Rojo Neón = Pérdidas  Verde Neón = Ganancias.")
            
            # 1. Conversión de Hora Server (UTC/MT5) a Hora Local de la Computadora
            # Asumimos que entrytime viene como timestamp UTC (unit='s')
            try:
                # Obtenemos la zona horaria local del sistema
                local_tz = datetime.now().astimezone().tzinfo
                
                # Convertimos: UTC -> Local
                # Nota: Si entrytime ya tiene info de zona, tz_localize('UTC') podría fallar, pero history_deals_get suele dar timestamp naive
                df_eff['local_entrytime'] = df_eff['entrytime'].dt.tz_localize('UTC').dt.tz_convert(local_tz)
                df_eff['local_hour'] = df_eff['local_entrytime'].dt.hour
            except Exception as e:
                # Fallback por si acaso
                df_eff['local_hour'] = df_eff['entrytime'].dt.hour
            
            # Preparar datos: Group by Day + Hour (Local)
            days_order = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            df_eff['day_cat'] = pd.Categorical(df_eff['day_name'], categories=days_order, ordered=True)
            
            heatmap_data = df_eff.groupby(['day_cat', 'local_hour'])['netpnl'].sum().reset_index()
            # Pivotear: Index=Día, Columns=Hora, Values=PnL
            heatmap_pivot = heatmap_data.pivot(index='day_cat', columns='local_hour', values='netpnl')
            
            # Rellenar horas faltantes con 0 para que la cuadrícula quede bonita
            all_hours = list(range(24))
            heatmap_pivot = heatmap_pivot.reindex(columns=all_hours, fill_value=0)
            heatmap_pivot = heatmap_pivot.reindex(index=days_order) # Asegurar orden de días
            
            # Plot
            z_vals = heatmap_pivot.values
            y_vals = heatmap_pivot.index.tolist()
            x_vals = heatmap_pivot.columns.tolist()
            
            max_val = np.nanmax(np.abs(z_vals)) if not np.all(np.isnan(z_vals)) else 100
            
            # Custom Colorscale: Rojo Neón -> Transparente -> Verde Neón
            neon_colorscale = [
                [0.0, 'rgba(255, 0, 80, 0.85)'],   # Bright Neon Red
                [0.5, 'rgba(0, 0, 0, 0.0)'],       # Transparent Black (Zero)
                [1.0, 'rgba(0, 255, 150, 0.85)']   # Bright Neon Green
            ]

            fig_death = go.Figure(data=go.Heatmap(
                z=z_vals, x=x_vals, y=y_vals,
                colorscale=neon_colorscale, 
                zmid=0, zmin=-max_val, zmax=max_val,
                xgap=2, ygap=2, # Separación para efecto grid estético
                hoverongaps=False,
                hovertemplate="<b>%{y}</b> a las <b>%{x}:00 (Local)</b><br>PnL Neto: <b>$%{z:,.2f}</b><extra></extra>"
            ))
            fig_death.update_layout(
                template="plotly_dark", height=450,
                xaxis=dict(
                    title="Hora del Día (Tu Horario Local)", 
                    tickmode='linear', 
                    dtick=1,
                    showgrid=False,
                    zeroline=False
                ),
                yaxis=dict(
                    title="",
                    showgrid=False,
                    zeroline=False
                ),
                paper_bgcolor='rgba(0,0,0,0)', 
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(family="Inter", color="#E2E8F0")
            )
            st.plotly_chart(fig_death, use_container_width=True)

        elif menu == "Data Journal":
            st.markdown("###  Bitácora de Operaciones")
            
            # MODIFICACIÓN: Filtros Separados (Tiempo + Sesión)
            col_filter_time, col_filter_session = st.columns(2)
            
            with col_filter_time:
                # Opciones de tiempo limpias + "Última Sesión Operada" (Día real)
                filter_options = [
                    "Todo el Historial", 
                    "Último Mes (30 Días)", 
                    "Última Semana (7 Días)", 
                    "Última Sesión Operada (Día)"
                ]
                # Default: Última Semana (Índice 2)
                time_filter = st.selectbox(" Filtrar Historial (Tiempo)", filter_options, index=2)
            
            with col_filter_session:
                # Nuevo filtro exclusivo para Sesiones
                session_options = ["Todas", "NY (New York)", "TK (Tokyo)", "LD (London)"]
                session_filter_val = st.selectbox(" Filtrar por Sesión", session_options)
            
            cutoff = None
            specific_day_filter = None
            
            # Lógica de Filtrado Temporal
            if "30 Días" in time_filter: 
                cutoff = datetime.now() - timedelta(days=30)
            elif "7 Días" in time_filter: 
                cutoff = datetime.now() - timedelta(days=7)
            elif "Última Sesión Operada" in time_filter:
                # Buscar el día de la última operación registrada
                if not df.empty:
                    last_trade_date = df['entrytime'].max().date()
                    specific_day_filter = last_trade_date
                    cutoff = datetime.combine(last_trade_date, dt_time.min) # Para depósitos
                else:
                    cutoff = datetime.now() # Fallback

            # --- Filtrado de Depósitos ---
            if 'deps' in st.session_state and st.session_state.deps is not None and not st.session_state.deps.empty:
                journal_deps = st.session_state.deps.copy()
                
                if 'Nota' not in journal_deps.columns and 'comment' in journal_deps.columns:
                    journal_deps.rename(columns={'comment': 'Nota'}, inplace=True)
                
                journal_deps['Tipo'] = journal_deps['Monto'].apply(lambda x: 'Depósito' if x > 0 else 'Retiro')
                
                # Aplicar filtro de fecha
                if cutoff: 
                    journal_deps = journal_deps[journal_deps['Fecha'] >= cutoff]
                    if specific_day_filter:
                        journal_deps = journal_deps[journal_deps['Fecha'].dt.date == specific_day_filter]
                
                # Nota: Los depósitos no tienen "Sesión" (NY/TK/LD) per se, así que no aplicamos session_filter_val aquí para no ocultarlos erróneamente.
                
                if not journal_deps.empty:
                    box_header("Movimientos de Capital (Funding)", "box-warning")
                    view_deps = journal_deps[['Fecha', 'Tipo', 'Monto', 'Nota']].copy()
                    view_deps.columns = ['Fecha', 'Tipo', 'Monto ($)', 'Nota']
                    view_deps = view_deps.sort_values('Fecha', ascending=False)
                    def color_deps(val):
                        color = '#10B981' if val > 0 else '#EF4444'
                        return f'color: {color}; font-weight: bold;'
                    st.dataframe(view_deps.style.map(color_deps, subset=['Monto ($)']).format({"Fecha": lambda x: x.strftime("%d-%m %H:%M"), "Monto ($)": "${:,.2f}"}), use_container_width=True, height=200, hide_index=True)
                    st.markdown("---")

            c_tr_head, c_tr_exp = st.columns([3, 1])
            with c_tr_head:
                title_suffix = f" - {session_filter_val}" if session_filter_val != "Todas" else ""
                box_header(f"Registro de Operaciones (Trading){title_suffix}", "box-primary")
            
            # --- Filtrado de Trades (Tiempo + Sesión) ---
            journal_trades = df.copy()
            journal_trades['Tipo'] = journal_trades['direction']
            
            # 1. Filtro Tiempo
            if cutoff: 
                journal_trades = journal_trades[journal_trades['entrytime'] >= cutoff]
            if specific_day_filter:
                journal_trades = journal_trades[journal_trades['entrytime'].dt.date == specific_day_filter]
            
            # 2. Filtro Sesión (AND)
            if session_filter_val != "Todas":
                journal_trades = journal_trades[journal_trades['session'] == session_filter_val]
            
            journal_trades = journal_trades.sort_values('entrytime', ascending=False)

            with c_tr_exp:
                if not journal_trades.empty:
                    csv_journal = convert_df_to_csv(journal_trades)
                    st.download_button(label=" Descargar Journal", data=csv_journal, file_name='trading_journal.csv', mime='text/csv')

            view = journal_trades[['entrytime', 'day_name', 'session', 'Tipo', 'volume', 'entryprice', 'sl', 'exitprice', 'netpnl', 'equity']].copy()
            view.columns = ['Fecha', 'Día', 'Sesión', 'Tipo', 'Lotes', 'Entrada', 'SL', 'Salida', 'PnL ($)', 'Balance']
            def color_pnl(val):
                if pd.isna(val): return ''
                color = '#10B981' if val > 0 else '#EF4444'
                return f'color: {color}; font-weight: bold;'
            st.dataframe(view.style.map(color_pnl, subset=['PnL ($)']).format({
                "Fecha": lambda x: x.strftime("%d-%m %H:%M"), "Lotes": "{:.2f}", "Entrada": "{:.5f}",
                "SL": "{:.5f}", "Salida": "{:.5f}", "PnL ($)": "${:.2f}", "Balance": "${:,.2f}"
            }), use_container_width=True, height=500, hide_index=True)
            
            period_profit = journal_trades['netpnl'].sum()
            total_trades_period = len(journal_trades)
            st.markdown("---")
            c_tot1, c_tot2, c_tot3 = st.columns([1, 1, 2])
            with c_tot1: st.metric("Beneficio Neto (Periodo)", f"${period_profit:,.2f}", delta=f"{total_trades_period} Trades")
            with c_tot3: st.caption(f"ℹ Filtro Activo: {time_filter} + Sesión {session_filter_val}.")

            # RESTAURACIÓN: Gráficos de Análisis Diario
            st.markdown("---")
            col_d1, col_d2 = st.columns(2)
            days_order = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            trades_per_day = df['day_name'].value_counts().reindex(days_order).fillna(0)
            
            with col_d1:
                box_header("Volumen de Operaciones por Día", "box-warning")
                fig_vol = px.bar(x=trades_per_day.index, y=trades_per_day.values, labels={'x': 'Día', 'y': 'Cantidad de Trades'}, color=trades_per_day.values, color_continuous_scale='Bluyl')
                fig_vol.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
                st.plotly_chart(fig_vol, use_container_width=True)
            
            pnl_per_day = df.groupby('day_name')['netpnl'].mean().reindex(days_order).fillna(0)
            with col_d2:
                box_header("Rendimiento Promedio por Día ($)", "box-success")
                fig_pnl = px.bar(x=pnl_per_day.index, y=pnl_per_day.values, labels={'x': 'Día', 'y': 'PnL Promedio ($)'}, color=pnl_per_day.values > 0, color_discrete_map={True: '#10B981', False: '#EF4444'})
                fig_pnl.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
                st.plotly_chart(fig_pnl, use_container_width=True)

        elif menu == "Journal Visual":
            st.markdown("###  Journal Visual")
            
            # --- NUEVA SECCIÓN: CALENDARIO ESTILO ZELLA ---
            box_header("Visual Calendar PnL", "box-primary")
            
            # Preparar datos de PnL Diario
            daily_pnl_data = df.groupby(df['entrytime'].dt.date)['netpnl'].sum()

            # Controles del Calendario
            col_cal_1, col_cal_2, col_cal_3 = st.columns([1, 1, 4])
            with col_cal_1:
                cal_year = st.selectbox("Año", range(2023, datetime.now().year + 2), index=list(range(2023, datetime.now().year + 2)).index(datetime.now().year))
            with col_cal_2:
                month_names = list(calendar.month_name)[1:]
                current_month_index = datetime.now().month - 1
                cal_month_name = st.selectbox("Mes", month_names, index=current_month_index)
                cal_month = month_names.index(cal_month_name) + 1
            
            # Lógica de construcción del Calendario
            cal_obj = calendar.Calendar(firstweekday=0) # Lunes = 0
            month_days = cal_obj.monthdayscalendar(cal_year, cal_month)
            
            # Estilos CSS específicos para la rejilla del calendario
            st.markdown("""
            <style>
                .calendar-grid {
                    display: grid;
                    grid-template-columns: repeat(7, 1fr);
                    gap: 12px;
                    margin-top: 20px;
                }
                .calendar-day-header {
                    text-align: center;
                    font-weight: 700;
                    color: #64748B;
                    text-transform: uppercase;
                    font-size: 12px;
                    padding-bottom: 8px;
                }
                .calendar-cell {
                    background-color: #1A202C;
                    border: 1px solid #2D3748;
                    border-radius: 8px;
                    height: 100px;
                    padding: 10px;
                    display: flex;
                    flex-direction: column;
                    justify-content: space-between;
                    transition: transform 0.2s;
                }
                .calendar-cell:hover {
                    border-color: #4A5568;
                    transform: scale(1.02);
                }
                .cell-date {
                    font-size: 14px;
                    font-weight: 600;
                    color: #A0AEC0;
                }
                .cell-pnl {
                    font-size: 16px;
                    font-weight: 800;
                    text-align: right;
                }
                .cell-win {
                    background-color: rgba(16, 185, 129, 0.15) !important;
                    border: 1px solid rgba(16, 185, 129, 0.4) !important;
                }
                .cell-loss {
                    background-color: rgba(239, 68, 68, 0.15) !important;
                    border: 1px solid rgba(239, 68, 68, 0.4) !important;
                }
                .cell-empty {
                    background-color: transparent;
                    border: none;
                }
                .pnl-green { color: #34D399; }
                .pnl-red { color: #F87171; }
            </style>
            """, unsafe_allow_html=True)

            # Renderizado del Grid
            days_header = ["LUN", "MAR", "MIÉ", "JUE", "VIE", "SÁB", "DOM"]
            
            # Construcción HTML
            html_cal = '<div class="calendar-grid">'
            
            # Headers
            for d in days_header:
                html_cal += f'<div class="calendar-day-header">{d}</div>'
            
            # Días
            for week in month_days:
                for day in week:
                    if day == 0:
                        html_cal += '<div class="calendar-cell cell-empty"></div>'
                    else:
                        current_date = date(cal_year, cal_month, day)
                        day_pnl = daily_pnl_data.get(current_date, 0.0)
                        
                        cell_class = ""
                        pnl_html = ""
                        
                        # Determinar estilo basado en PnL
                        if day_pnl > 0:
                            cell_class = "cell-win"
                            pnl_html = f'<span class="cell-pnl pnl-green">+${day_pnl:,.2f}</span>'
                        elif day_pnl < 0:
                            cell_class = "cell-loss"
                            pnl_html = f'<span class="cell-pnl pnl-red">-${abs(day_pnl):,.2f}</span>'
                        else:
                            # Chequear si hubo trades ese día con PnL 0 (breakeven) o simplemente no hubo trades
                            # Si no está en el índice del groupby, es 0 y no hubo actividad relevante (o net 0)
                            if current_date in daily_pnl_data.index and daily_pnl_data[current_date] == 0:
                                pnl_html = '<span class="cell-pnl" style="color: #94A3B8;">$0.00</span>'
                            else:
                                pnl_html = '<span class="cell-pnl" style="color: #475569;">-</span>'

                        html_cal += f'<div class="calendar-cell {cell_class}"><span class="cell-date">{day}</span>{pnl_html}</div>'
            
            html_cal += '</div>'
            st.markdown(html_cal, unsafe_allow_html=True)
            
            st.markdown("---")
            # --- FIN SECCIÓN CALENDARIO ---

            # --- SISTEMA DE PERSISTENCIA LOCAL ---
            JOURNAL_DIR = "_journal_data"
            IMG_DIR = os.path.join(JOURNAL_DIR, "images")
            DB_FILE = os.path.join(JOURNAL_DIR, "db.json")

            # Inicializar directorios si no existen
            if not os.path.exists(JOURNAL_DIR):
                os.makedirs(JOURNAL_DIR)
                os.makedirs(IMG_DIR)
                with open(DB_FILE, 'w') as f: json.dump([], f)
            
            # Función para cargar entradas
            def load_entries():
                try:
                    with open(DB_FILE, 'r') as f:
                        return json.load(f)
                except: return []

            # Función para guardar entrada
            def save_new_entry(entry_data):
                entries = load_entries()
                entries.insert(0, entry_data) # Lo más nuevo primero
                with open(DB_FILE, 'w') as f:
                    json.dump(entries, f, indent=4)

            # Función para actualizar la base de datos completa (Edición)
            def update_db(entries):
                with open(DB_FILE, 'w') as f:
                    json.dump(entries, f, indent=4)

            # --- FORMULARIO DE NUEVA ENTRADA ---
            with st.expander(" Crear Nueva Entrada", expanded=False):
                with st.form("journal_form", clear_on_submit=True):
                    c_meta1, c_meta2, c_meta3 = st.columns([2, 1, 1])
                    
                    # Selector de Trade para vincular datos
                    trade_options = {}
                    if not df.empty:
                        # Crear diccionario {Label: Data} para los últimos 50 trades
                        last_trades = df.sort_values('entrytime', ascending=False).head(50)
                        for _, row in last_trades.iterrows():
                            lbl = f"{row['entrytime'].strftime('%Y-%m-%d %H:%M')}  {row['symbol']}  {row['direction']}  ${row['netpnl']:.2f}"
                            trade_options[lbl] = row.to_dict()
                    
                    with c_meta1:
                        title = st.text_input("Título de la Entrada", placeholder="Ej: Setup de Reversión...")
                    with c_meta2:
                        # MODIFICACIÓN: Selector de Sesión
                        session_select = st.selectbox("Sesión", ["NY", "TK", "LD"])
                    with c_meta3:
                        linked_trade_lbl = st.selectbox("Vincular Operación", ["Ninguna"] + list(trade_options.keys()))
                    
                    content = st.text_area("Análisis / Psicología", placeholder="¿Qué viste? ¿Cómo te sentiste? Usa Markdown aquí...", height=150)
                    uploaded_img = st.file_uploader("Adjuntar Gráfico (Captura)", type=['png', 'jpg', 'jpeg'])
                    
                    # MODIFICACIÓN: Botón de guardado PRIMARIO para distinguirlo de las flechas
                    submitted = st.form_submit_button(" Guardar Entrada", type="primary")
                    
                    if submitted:
                        if not title:
                            st.error("El título es obligatorio.")
                        else:
                            # Procesar Imagen
                            img_path_rel = None
                            if uploaded_img is not None:
                                file_ext = uploaded_img.name.split('.')[-1]
                                unique_name = f"{uuid.uuid4()}.{file_ext}"
                                abs_path = os.path.join(IMG_DIR, unique_name)
                                with open(abs_path, "wb") as f:
                                    f.write(uploaded_img.getbuffer())
                                img_path_rel = unique_name
                            
                            # Procesar Datos del Trade Vinculado
                            trade_meta = None
                            tag_type = "neu"
                            if linked_trade_lbl != "Ninguna":
                                t_data = trade_options[linked_trade_lbl]
                                trade_meta = {
                                    "symbol": t_data['symbol'],
                                    "pnl": t_data['netpnl'],
                                    "type": t_data['direction'],
                                    "time": str(t_data['entrytime'])
                                }
                                tag_type = "win" if t_data['netpnl'] > 0 else "loss"

                            # Construir Objeto
                            # MODIFICADO: AHORA USAMOS 'PAGES' en lugar de content/image directo
                            new_entry = {
                                "id": str(uuid.uuid4()),
                                "timestamp": datetime.now().isoformat(),
                                "title": title,
                                "session": session_select, 
                                "trade_data": trade_meta,
                                "tag_type": tag_type,
                                # Estructura multi-página
                                "pages": [
                                    {
                                        "content": content,
                                        "image": img_path_rel
                                    }
                                ]
                            }
                            
                            save_new_entry(new_entry)
                            st.success("Entrada guardada correctamente.")
                            time.sleep(1) # Pequeña pausa para UX
                            st.rerun()

            # --- FEED DE ENTRADAS (TABS POR SESIÓN) ---
            st.markdown("---")
            all_entries = load_entries()
            
            # --- MIGRACIÓN AUTOMÁTICA DE DATOS VIEJOS ---
            data_migrated = False
            for entry in all_entries:
                if "pages" not in entry:
                    # Convertir formato viejo a nuevo
                    entry["pages"] = [{
                        "content": entry.get("content", ""),
                        "image": entry.get("image", None)
                    }]
                    # Limpiar campos viejos para evitar confusión futura
                    if "content" in entry: del entry["content"]
                    if "image" in entry: del entry["image"]
                    data_migrated = True
            
            if data_migrated:
                update_db(all_entries)
                st.rerun()

            if not all_entries:
                st.info("Tu journal está vacío. ¡Crea tu primera entrada arriba!")
            else:
                # Crear Pestañas
                tab_ny, tab_tk, tab_ld = st.tabs([" Registro de NY", " Registro de TK", " Registro de LD"])
                
                # Función Helper para Renderizar Lista
                def render_session_feed(target_session, entries_list):
                    indices = [i for i, e in enumerate(entries_list) if e.get('session', 'NY') == target_session]
                    
                    if not indices:
                        st.caption(f"No hay registros para la sesión {target_session}.")
                        return

                    for idx in indices:
                        entry = entries_list[idx]
                        pages = entry.get("pages", [])
                        
                        # --- ESTADO LOCAL PARA PAGINACIÓN ---
                        # Usamos keys únicos basados en el ID de la entrada
                        page_key = f"page_idx_{entry['id']}"
                        if page_key not in st.session_state:
                            st.session_state[page_key] = 0
                        
                        current_page_idx = st.session_state[page_key]
                        
                        # Asegurar que el índice es válido (por si se borró una página)
                        if current_page_idx >= len(pages):
                            current_page_idx = len(pages) - 1
                            st.session_state[page_key] = current_page_idx

                        date_obj = datetime.fromisoformat(entry['timestamp'])
                        date_str = date_obj.strftime("%d/%m")
                        
                        # Construir Título
                        header_emoji = ""
                        trade_info_str = ""
                        if entry.get('trade_data'):
                            td = entry['trade_data']
                            symbol = td['symbol']
                            pnl = td['pnl']
                            res_icon = "" if pnl > 0 else ""
                            trade_info_str = f"  {res_icon} {symbol} (${pnl:,.2f})"
                            header_emoji = ""
                        
                        expander_label = f"{header_emoji} {date_str} - {entry['title']}{trade_info_str}"
                        
                        # Menú Desplegable
                        with st.expander(expander_label):
                            e_id = entry['id']
                            
                            # --- GESTIÓN DE ENTRADA (BORRAR) ---
                            # Usamos columnas para empujar el botón a la derecha
                            c_void, c_trash = st.columns([20, 1]) 
                            with c_trash:
                                if st.button("", key=f"delete_entry_{e_id}", help="Eliminar esta entrada permanentemente"):
                                    entries_list.pop(idx)
                                    update_db(entries_list)
                                    st.toast("Entrada eliminada")
                                    time.sleep(0.5)
                                    st.rerun()

                            # --- CSS ESPECÍFICO PARA FLECHAS STEALTH (Corregido) ---
                            st.markdown("""
                            <style>
                            /* Aseguramos que los botones dentro de las columnas laterales sean transparentes */
                            div[data-testid="column"] button.stealth-btn {
                                background-color: transparent !important;
                                border: 1px solid transparent !important;
                                color: rgba(160, 174, 192, 0.5) !important; /* Gris transparente */
                                font-size: 20px !important;
                                padding: 0 !important;
                            }
                            div[data-testid="column"] button.stealth-btn:hover {
                                color: rgba(255, 255, 255, 0.9) !important;
                                background-color: transparent !important;
                                transform: scale(1.2);
                            }
                            div[data-testid="column"] button.stealth-btn:active,
                            div[data-testid="column"] button.stealth-btn:focus {
                                background-color: transparent !important;
                                border-color: transparent !important;
                                box-shadow: none !important;
                                color: white !important;
                            }
                            </style>
                            """, unsafe_allow_html=True)

                            # --- LAYOUT DE 3 COLUMNAS ---
                            col_nav_l, col_content, col_nav_r = st.columns([1, 15, 1])
                            
                            # --- BOTÓN IZQUIERDO ---
                            with col_nav_l:
                                st.write("")
                                st.write("")
                                st.write("")
                                st.write("")
                                # Usamos key única y no aplicamos estilo inline porque Streamlit no lo permite directmente en el botón, 
                                # confiamos en el CSS global inyectado arriba que targetea los botones en estas columnas específicas.
                                if st.button("", key=f"prev_{e_id}", disabled=(current_page_idx == 0)):
                                    st.session_state[page_key] = max(0, current_page_idx - 1)
                                    st.rerun()

                            # --- CONTENIDO CENTRAL ---
                            with col_content:
                                # Header de página: Indicador y acciones integradas
                                c_info, c_actions = st.columns([4, 1])
                                with c_info:
                                    st.caption(f"Página {current_page_idx + 1} de {len(pages)}")
                                with c_actions:
                                    # Toolbar minimalista
                                    col_add, col_del = st.columns(2)
                                    with col_add:
                                        if st.button("", key=f"add_{e_id}", help="Nueva Página"):
                                            entry["pages"].append({"content": "", "image": None})
                                            st.session_state[page_key] = len(entry["pages"]) - 1
                                            update_db(entries_list)
                                            st.rerun()
                                    with col_del:
                                        if st.button("", key=f"del_{e_id}", help="Borrar Página"):
                                            if len(pages) > 1:
                                                entry["pages"].pop(current_page_idx)
                                                st.session_state[page_key] = max(0, current_page_idx - 1)
                                                update_db(entries_list)
                                                st.rerun()
                                
                                # --- EDITOR DE CONTENIDO ---
                                current_page_data = pages[current_page_idx]
                                
                                new_content = st.text_area(
                                    label="Nota",
                                    value=current_page_data.get('content', ''), 
                                    height=250,
                                    key=f"txt_{e_id}_{current_page_idx}",
                                    label_visibility="collapsed",
                                    placeholder=f"Escribe aquí tus observaciones de la página {current_page_idx + 1}..."
                                )
                                
                                # Auto-guardado
                                if new_content != current_page_data.get('content', ''):
                                    entry["pages"][current_page_idx]['content'] = new_content
                                    update_db(entries_list)

                                # --- VISUALIZADOR DE IMAGEN ---
                                img_val = current_page_data.get('image')
                                if img_val:
                                    img_full_path = os.path.join(IMG_DIR, img_val)
                                    if os.path.exists(img_full_path):
                                        st.image(img_full_path, use_container_width=True)
                                
                                # --- CARGADOR DE IMAGEN (DISCRETO AL FINAL) ---
                                uploaded_new = st.file_uploader(
                                    "Adjuntar evidencia visual (Arrastra aquí)", 
                                    type=['png', 'jpg', 'jpeg'], 
                                    key=f"up_{e_id}_{current_page_idx}"
                                )
                                
                                if uploaded_new is not None:
                                    file_ext = uploaded_new.name.split('.')[-1]
                                    unique_name = f"{uuid.uuid4()}.{file_ext}"
                                    abs_path = os.path.join(IMG_DIR, unique_name)
                                    with open(abs_path, "wb") as f:
                                        f.write(uploaded_new.getbuffer())
                                    
                                    entry["pages"][current_page_idx]['image'] = unique_name
                                    update_db(entries_list)
                                    st.toast("Imagen guardada!")
                                    time.sleep(1)
                                    st.rerun()

                            # --- BOTÓN DERECHO ---
                            with col_nav_r:
                                st.write("")
                                st.write("")
                                st.write("")
                                st.write("")
                                if st.button("", key=f"next_{e_id}", disabled=(current_page_idx == len(pages) - 1)):
                                    st.session_state[page_key] = min(len(pages) - 1, current_page_idx + 1)
                                    st.rerun()

                with tab_ny:
                    render_session_feed("NY", all_entries)
                with tab_tk:
                    render_session_feed("TK", all_entries)
                with tab_ld:
                    render_session_feed("LD", all_entries)

    else:
        st.markdown("""
        <div style="display: flex; justify-content: center; align-items: center; height: 80vh;">
            <div class="box box-primary" style="width: 500px; text-align: center; padding: 60px; background-color: #1A202C; border: 1px solid #2D3748; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);">
                <div style="font-size: 72px; background: linear-gradient(to right, #3B82F6, #8B5CF6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 30px;"><i class="fas fa-chart-line"></i></div>
                <h2 style="color: #F3F4F6; margin-bottom: 15px; font-weight: 800; font-size: 28px;">Micro-Fund Audit Tool</h2>
                <p style="color: #A0AEC0; font-size: 16px; line-height: 1.6; margin-bottom: 30px;">
                    Infraestructura de auditoría forense para trading institucional.<br>
                    Sincroniza tu terminal MT5 para desplegar el análisis.
                </p>
                <div style="display: inline-block; padding: 8px 16px; background: #2D3748; border-radius: 20px; font-size: 12px; color: #63B3ED; font-weight: 600;">
                    ● System Ready
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)