//+------------------------------------------------------------------+
//                                     Sovereign_EA_V30_0.mq5        
//                                  Copyright 2024, TradingAlgo      
//                        Agente Maestro: QUANTUM EDITION V30.0      
//+------------------------------------------------------------------+
#property copyright "Copyright 2024, TradingAlgo"
#property link      "https://www.mql5.com/en/users/nuevoadmin"
#property version   "30.00" // V30: Quantum Engine Integration
#property strict
#property tester_file "..\\Files\\Sovereign_Config_50001.csv"

#include <Trade\Trade.mqh>
#include <Trade\SymbolInfo.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>

/*
   OPERATING CRITERIA (Sovereign Quantum V30.0):
   1. F(t-1) PARITY: Operates ONLY on closed bars (Zero Lag Policy).
   2. QUANTUM HMM REGIME: Uses GJR-GARCH(1,1) Volatility + Kalman Filter Gate.
   3. ADAPTIVE Z-SCORE: ML Strength scales with Online Concept Drift mitigation.
   4. DYNAMIC JUMP-DIFFUSION: Nu and Lambda calibrate every 500 bars.
   5. RISK: Fixed % balance per trade. Partial close 70% at 1:2 R/R.
*/

//--- INPUTS
input string G1 = "--- Quantum Risk Parameters ---";
input double InpMinStrength   = 0.35;    // Min ML Strength for Entry
input double InpVolMultiplier = 2.5;     // Multiplicador de Volatilidad para SL (ej. 2.5 sigma)
input double InpRewardRisk    = 2.0;     // Ratio Riesgo/Beneficio (TP = SL * RR)
input bool   InpUsePartials   = true;    // Use Partial Closure
input int    InpMagic         = 50001;   // Magic Number (V30 Series)
input bool   InpLoadRobustConfigCsv = true;
input string InpRobustConfigCsv     = "Sovereign_Config_50001.csv";

input string G2 = "--- Risk Management ---";
input double InpRiskPercent   = 1.0;     // Risk per Trade (%)
input double InpMaxLot        = 10.0;    // Max allowed Lot

input string G3 = "--- Layered Edge Filters (50001) ---";
input bool   InpUseLayerFilters      = true;       // Enable 50001 defensive layers
input int    InpSession1StartHour    = 7;          // London start, inclusive
input int    InpSession1EndHour      = 13;         // London end, exclusive
input int    InpSession2StartHour    = 20;         // Late start, inclusive
input int    InpSession2EndHour      = 24;         // Late end, exclusive
input double InpLayerMinStrength     = 0.50;       // Tick OOS layer threshold
input double InpMinSigmaProjected    = 0.0008412616967549172;
input double InpMaxSigmaProjected    = 0.0032338662645819277;
input int    InpMaxSpreadPoints      = 80;         // Defensive spread ceiling
input int    InpMaxRecentLosses      = 4;          // Pause after N consecutive losses
input int    InpLossLookbackDays     = 30;         // History window for loss monitor
input bool   InpExitOnRegimeFlip     = true;       // Close if signal flips against position
input int    InpMaxBarsInTrade       = 96;         // Time stop in M15 bars
input int    InpMinBarsBeforePartial = 12;         // Avoid noisy early partial logic
input bool   InpExitOnWeakStrength   = true;       // Close if strength deteriorates after warmup
input double InpWeakExitStrength     = 0.45;       // Weak-strength exit threshold
input double InpWeakPartialFactor    = 0.70;       // Earlier partial in weak regime

input string G4 = "--- Indicator Link ---";
input string InpIndiPath      = "Sovereign\\Sovereign_50001_Signal"; // V8.1 Required

input string G5 = "--- Visual Dashboard (Quantum) ---";
input color  InpDashColor     = clrAqua; 
input int    InpBase_X        = 20;      
input int    InpBase_Y        = 200;     

//--- Globals
CTrade         m_trade;
CSymbolInfo    m_symbol;
CPositionInfo  m_position;
CAccountInfo   m_account;
int            g_handle = INVALID_HANDLE;
double         g_last_strength = 0.0;
double         g_last_hmm = 0.5;
double         g_last_sig_proj = 0.0;
string         g_status = "SCANNING";
double         g_min_strength = 0.35;
double         g_vol_multiplier = 2.5;
double         g_reward_risk = 2.0;
double         g_risk_percent = 1.0;
double         g_max_lot = 10.0;
bool           g_use_partials = true;
bool           g_use_layer_filters = true;
int            g_session1_start_hour = 7;
int            g_session1_end_hour = 13;
int            g_session2_start_hour = 20;
int            g_session2_end_hour = 24;
double         g_layer_min_strength = 0.50;
double         g_min_sigma_projected = 0.0008412616967549172;
double         g_max_sigma_projected = 0.0032338662645819277;
int            g_max_spread_points = 80;
int            g_max_recent_losses = 4;
int            g_loss_lookback_days = 30;
bool           g_exit_on_regime_flip = true;
int            g_max_bars_in_trade = 96;
int            g_min_bars_before_partial = 12;
bool           g_exit_on_weak_strength = true;
double         g_weak_exit_strength = 0.45;
double         g_weak_partial_factor = 0.70;
bool           g_layer_allows = true;
string         g_layer_status = "LAYERS READY";

bool CsvBool(string value) {
    StringToLower(value);
    return (value == "true"  value == "1"  value == "yes"  value == "si");
}

void LoadRobustConfigCsv() {
    g_min_strength = InpMinStrength;
    g_vol_multiplier = InpVolMultiplier;
    g_reward_risk = InpRewardRisk;
    g_risk_percent = InpRiskPercent;
    g_max_lot = InpMaxLot;
    g_use_partials = InpUsePartials;
    g_use_layer_filters = InpUseLayerFilters;
    g_session1_start_hour = InpSession1StartHour;
    g_session1_end_hour = InpSession1EndHour;
    g_session2_start_hour = InpSession2StartHour;
    g_session2_end_hour = InpSession2EndHour;
    g_layer_min_strength = InpLayerMinStrength;
    g_min_sigma_projected = InpMinSigmaProjected;
    g_max_sigma_projected = InpMaxSigmaProjected;
    g_max_spread_points = InpMaxSpreadPoints;
    g_max_recent_losses = InpMaxRecentLosses;
    g_loss_lookback_days = InpLossLookbackDays;
    g_exit_on_regime_flip = InpExitOnRegimeFlip;
    g_max_bars_in_trade = InpMaxBarsInTrade;
    g_min_bars_before_partial = InpMinBarsBeforePartial;
    g_exit_on_weak_strength = InpExitOnWeakStrength;
    g_weak_exit_strength = InpWeakExitStrength;
    g_weak_partial_factor = InpWeakPartialFactor;
    if(!InpLoadRobustConfigCsv) return;

    int handle = FileOpen(InpRobustConfigCsv, FILE_READ  FILE_CSV  FILE_ANSI, ',');
    if(handle == INVALID_HANDLE) {
        Print("INFO: Robust config CSV not found. Using EA inputs.");
        return;
    }

    string cols[42], vals[42];
    for(int i=0; i<42 && !FileIsEnding(handle); i++) cols[i] = FileReadString(handle);
    if(!FileIsEnding(handle)) {
        for(int i=0; i<42 && !FileIsEnding(handle); i++) vals[i] = FileReadString(handle);
        if(StringLen(vals[5]) > 0) g_min_strength = StringToDouble(vals[5]);
        if(StringLen(vals[6]) > 0) g_vol_multiplier = StringToDouble(vals[6]);
        if(StringLen(vals[7]) > 0) g_reward_risk = StringToDouble(vals[7]);
        if(StringLen(vals[9]) > 0) g_risk_percent = StringToDouble(vals[9]);
        if(StringLen(vals[10]) > 0) g_max_lot = StringToDouble(vals[10]);
        if(StringLen(vals[11]) > 0) g_use_partials = CsvBool(vals[11]);
        if(StringLen(vals[23]) > 0) g_use_layer_filters = CsvBool(vals[23]);
        if(StringLen(vals[24]) > 0) g_session1_start_hour = (int)StringToInteger(vals[24]);
        if(StringLen(vals[25]) > 0) g_session1_end_hour = (int)StringToInteger(vals[25]);
        if(StringLen(vals[26]) > 0) g_session2_start_hour = (int)StringToInteger(vals[26]);
        if(StringLen(vals[27]) > 0) g_session2_end_hour = (int)StringToInteger(vals[27]);
        if(StringLen(vals[28]) > 0) g_layer_min_strength = StringToDouble(vals[28]);
        if(StringLen(vals[29]) > 0) g_min_sigma_projected = StringToDouble(vals[29]);
        if(StringLen(vals[30]) > 0) g_max_sigma_projected = StringToDouble(vals[30]);
        if(StringLen(vals[31]) > 0) g_max_spread_points = (int)StringToInteger(vals[31]);
        if(StringLen(vals[32]) > 0) g_max_recent_losses = (int)StringToInteger(vals[32]);
        if(StringLen(vals[33]) > 0) g_loss_lookback_days = (int)StringToInteger(vals[33]);
        if(StringLen(vals[34]) > 0) g_exit_on_regime_flip = CsvBool(vals[34]);
        if(StringLen(vals[35]) > 0) g_max_bars_in_trade = (int)StringToInteger(vals[35]);
        if(StringLen(vals[38]) > 0) g_min_bars_before_partial = (int)StringToInteger(vals[38]);
        if(StringLen(vals[39]) > 0) g_exit_on_weak_strength = CsvBool(vals[39]);
        if(StringLen(vals[40]) > 0) g_weak_exit_strength = StringToDouble(vals[40]);
        if(StringLen(vals[41]) > 0) g_weak_partial_factor = StringToDouble(vals[41]);
        g_min_strength = MathMax(g_min_strength, g_layer_min_strength);
        PrintFormat("Robust Config Loaded: strength=%.2f vol_mult=%.2f rr=%.2f risk=%.2f max_lot=%.2f partials=%s layers=%s",
                    g_min_strength, g_vol_multiplier, g_reward_risk, g_risk_percent, g_max_lot,
                    g_use_partials ? "true" : "false",
                    g_use_layer_filters ? "true" : "false");
    }
    FileClose(handle);
}

//+------------------------------------------------------------------+
// Expert initialization function                                   
//+------------------------------------------------------------------+
int OnInit() {
    if(!m_symbol.Name(_Symbol)) return(INIT_FAILED);
    LoadRobustConfigCsv();
    m_trade.SetExpertMagicNumber(InpMagic);
    
    g_handle = iCustom(_Symbol, _Period, InpIndiPath);
    if(g_handle == INVALID_HANDLE) {
        Print("CRITICAL ERROR: Could NOT load Quantum Indicator: ", InpIndiPath);
        return(INIT_FAILED);
    }
    
    Print("Sovereign 50001 EA initialized successfully.");
    return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
// Expert deinitialization function                                 
//+------------------------------------------------------------------+
void OnDeinit(const int reason) {
    IndicatorRelease(g_handle);
    ObjectsDeleteAll(0, "SOV_EA_");
}

//+------------------------------------------------------------------+
// Expert tick function                                             
//+------------------------------------------------------------------+
void OnTick() {
    // 1. Fetch closed-bar signal (Buff 18=Regime, 17=Strength, 15=HMM Prob, 32=Sig Proj)
    double regime_arr[1], strength_arr[1], prob_arr[1], sig_arr[1];
    const int signal_shift = 1;
    if(CopyBuffer(g_handle, 18, signal_shift, 1, regime_arr) <= 0) return;
    if(CopyBuffer(g_handle, 17, signal_shift, 1, strength_arr) <= 0) return;
    if(CopyBuffer(g_handle, 15, signal_shift, 1, prob_arr) <= 0) return;
    if(CopyBuffer(g_handle, 32, signal_shift, 1, sig_arr) <= 0) return; // Varianza Proyectada
    
    int    regime   = (int)regime_arr[0];
    double strength = strength_arr[0];
    double prob     = (prob_arr[0] > 1.0) ? 0.5 : prob_arr[0];
    double sig_proj = sig_arr[0];
    if(!MathIsValidNumber(strength)  !MathIsValidNumber(prob)  !MathIsValidNumber(sig_proj)) {
        g_status = "WAITING VALID SIGNAL";
        g_layer_status = "WAITING: SIGNAL NAN";
        g_layer_allows = false;
        DrawDashboard();
        return;
    }
    if(strength < 0.0  strength > 1.0) strength = MathMax(0.0, MathMin(1.0, strength));
    if(prob < 0.0  prob > 1.0) prob = 0.5;
    if(sig_proj <= 0.0) {
        g_status = "WAITING VALID SIGMA";
        g_layer_status = "WAITING: SIGMA";
        g_layer_allows = false;
        DrawDashboard();
        return;
    }
    
    g_last_strength = strength;
    g_last_hmm      = prob;
    g_last_sig_proj = sig_proj;
    g_layer_allows  = LayerFiltersAllow(strength, sig_proj);

    // 2. Position Management
    int total = PositionsTotal();
    bool has_position = false;
    for(int i=total-1; i>=0; i--) {
        if(m_position.SelectByIndex(i)) {
            if(m_position.Magic() == InpMagic && m_position.Symbol() == _Symbol) {
                has_position = true;
                g_status = "QUANTUM TRADING (" + (m_position.PositionType()==POSITION_TYPE_BUY?"Buy":"Sell") + ")";
                ManagePosition(regime);
                break;
            }
        }
    }
    
    if(!has_position) g_status = "SCANNING MARKET";

    // 3. Trade Entry (Only on New Bar)
    if(IsNewBar()) {
        if(!has_position && regime != 0 && strength >= g_min_strength && g_layer_allows) {
            ExecuteOrder(regime, strength, sig_proj);
        }
    }
    
    DrawDashboard();
}

//+------------------------------------------------------------------+
// Order Execution (Volatility Targeting)                           
//+------------------------------------------------------------------+
void ExecuteOrder(int type, double strength, double sig_proj) {
    m_symbol.RefreshRates();
    double price = (type == 1) ? m_symbol.Ask() : m_symbol.Bid();
    
    // Volatility Targeting: Distancia = Precio * Volatilidad Logartmica * Multiplicador
    double vol_distance_price = price * sig_proj * g_vol_multiplier;
    
    // Garantizar un mnimo estructural (evitar stop loss menores al spread)
    double min_sl_price = (m_symbol.Ask() - m_symbol.Bid()) * 3.0; // Mnimo 3x Spread
    vol_distance_price = MathMax(vol_distance_price, min_sl_price);

    double sl = (type == 1) ? price - vol_distance_price : price + vol_distance_price;
    double tp_distance = vol_distance_price * g_reward_risk;
    double tp = (type == 1) ? price + tp_distance : price - tp_distance;
    
    // Convertir distancia en precio a puntos para el clculo de lote
    int sl_pts = (int)(vol_distance_price / m_symbol.Point());
    
    double lot = CalculateLot(g_risk_percent, sl_pts);
    lot = MathMin(g_max_lot, MathMax(0.01, lot));
    
    ENUM_ORDER_TYPE ord_type = (type == 1) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
    string comment = "Q-Vol [sigma:" + DoubleToString(sig_proj*100, 2) + "%]";
    
    if(m_trade.PositionOpen(_Symbol, ord_type, lot, price, sl, tp, comment)) {
        PrintFormat("Trade Opened. Lot: %.2f  Dynamic SL Pts: %d", lot, sl_pts);
    }
}

//+------------------------------------------------------------------+
// Position Management (Dynamic Partials)                           
//+------------------------------------------------------------------+
void ManagePosition(int current_regime) {
    int bars_held = 0;
    int period_seconds = PeriodSeconds(_Period);
    if(period_seconds > 0) {
        bars_held = (int)((TimeCurrent() - m_position.Time()) / period_seconds);
    }

    if(g_use_layer_filters) {
        if(g_exit_on_regime_flip) {
            if(m_position.PositionType() == POSITION_TYPE_BUY && current_regime == -1) {
                m_trade.PositionClose(m_position.Ticket());
                Print("Sovereign 50001 Layer: closed BUY on regime flip.");
                return;
            }
            if(m_position.PositionType() == POSITION_TYPE_SELL && current_regime == 1) {
                m_trade.PositionClose(m_position.Ticket());
                Print("Sovereign 50001 Layer: closed SELL on regime flip.");
                return;
            }
        }
        if(g_exit_on_weak_strength && bars_held >= g_min_bars_before_partial && g_last_strength < g_weak_exit_strength) {
            m_trade.PositionClose(m_position.Ticket());
            PrintFormat("Sovereign 50001 Layer: closed by weak strength %.3f after %d bars.", g_last_strength, bars_held);
            return;
        }
        if(g_max_bars_in_trade > 0 && bars_held >= g_max_bars_in_trade) {
            m_trade.PositionClose(m_position.Ticket());
            PrintFormat("Sovereign 50001 Layer: closed by time stop after %d bars.", bars_held);
            return;
            }
    }

    if(!g_use_partials) return;
    if(m_position.PositionType() != POSITION_TYPE_BUY && m_position.PositionType() != POSITION_TYPE_SELL) return;

    double entry = m_position.PriceOpen();
    double current = m_position.PriceCurrent();
    double sl_level = m_position.StopLoss();
    
    // Calcular dinmicamente el riesgo inicial expuesto
    double initial_risk_price = MathAbs(entry - sl_level);
    if(initial_risk_price < m_symbol.Point()) return; // SL ya movido a BE

    double profit_price = (m_position.PositionType()==POSITION_TYPE_BUY) ? (current - entry) : (entry - current);
    
    // Target para parciales (ej. 1:1 o 1:1.5 dependiendo del RewardRisk)
    if(bars_held < g_min_bars_before_partial) return;
    double partial_factor = (g_last_strength < g_layer_min_strength) ? g_weak_partial_factor : 1.0;
    double partial_target_price = initial_risk_price * (g_reward_risk / 1.5) * partial_factor; 

    if(profit_price >= partial_target_price) {
        double vol = NormalizeDouble(m_position.Volume() * 0.7, 2);
        if(vol >= 0.01) {
            if(m_trade.PositionClosePartial(m_position.Ticket(), vol)) {
                m_trade.PositionModify(m_position.Ticket(), entry, m_position.TakeProfit());
                Print("Sovereign Quantum: Partial Executed. Risk Eliminated.");
            }
        }
    }
}

//+------------------------------------------------------------------+
// Risk Utility                                                     
//+------------------------------------------------------------------+
double CalculateLot(double risk_pct, int sl_pts) {
    double tick_val = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
    double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
    if(sl_pts <= 0  tick_val <= 0) return 0.01;
    
    double risk_money = AccountInfoDouble(ACCOUNT_BALANCE) * (risk_pct / 100.0);
    double lot = risk_money / (sl_pts * (tick_val / tick_size * m_symbol.Point()));
    return NormalizeDouble(lot, 2);
}

bool HourInWindow(int hour, int start_hour, int end_hour) {
    if(start_hour == end_hour) return true;
    if(start_hour < end_hour) return (hour >= start_hour && hour < end_hour);
    return (hour >= start_hour  hour < end_hour);
}

int RecentConsecutiveLosses() {
    if(g_max_recent_losses <= 0) return 0;
    datetime to_time = TimeCurrent();
    datetime from_time = to_time - (datetime)(g_loss_lookback_days * 86400);
    if(!HistorySelect(from_time, to_time)) return 0;

    int losses = 0;
    for(int i=HistoryDealsTotal()-1; i>=0; i--) {
        ulong ticket = HistoryDealGetTicket(i);
        if(ticket == 0) continue;
        if((long)HistoryDealGetInteger(ticket, DEAL_MAGIC) != InpMagic) continue;
        if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol) continue;
        if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
        double pnl = HistoryDealGetDouble(ticket, DEAL_PROFIT)
                   + HistoryDealGetDouble(ticket, DEAL_SWAP)
                   + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
        if(pnl < 0.0) losses++;
        else if(pnl > 0.0) break;
        if(losses >= g_max_recent_losses) break;
    }
    return losses;
}

bool LayerFiltersAllow(double strength, double sig_proj) {
    if(!g_use_layer_filters) {
        g_layer_status = "LAYERS OFF";
        return true;
    }

    MqlDateTime dt;
    TimeToStruct(TimeCurrent(), dt);
    bool in_session = HourInWindow(dt.hour, g_session1_start_hour, g_session1_end_hour)
                    HourInWindow(dt.hour, g_session2_start_hour, g_session2_end_hour);
    if(!in_session) {
        g_layer_status = "BLOCK: SESSION";
        return false;
    }

    if(strength < g_layer_min_strength) {
        g_layer_status = "BLOCK: STRENGTH";
        return false;
    }

    if(sig_proj < g_min_sigma_projected  sig_proj > g_max_sigma_projected) {
        g_layer_status = "BLOCK: SIGMA";
        return false;
    }

    m_symbol.RefreshRates();
    double spread_points = (m_symbol.Ask() - m_symbol.Bid()) / m_symbol.Point();
    if(g_max_spread_points > 0 && spread_points > g_max_spread_points) {
        g_layer_status = "BLOCK: SPREAD";
        return false;
    }

    int recent_losses = RecentConsecutiveLosses();
    if(g_max_recent_losses > 0 && recent_losses >= g_max_recent_losses) {
        g_layer_status = "PAUSE: LOSS STREAK";
        return false;
    }

    g_layer_status = "LAYERS PASS";
    return true;
}

//+------------------------------------------------------------------+
// Visual Dashboard (Quantum Enhanced)                              
//+------------------------------------------------------------------+
void DrawDashboard() {
    string prefix = "SOV_EA_";
    int y = InpBase_Y;
    int x = InpBase_X;
    
    color str_col = (g_last_strength >= g_min_strength) ? clrSpringGreen : clrTomato;
    color hmm_col = (g_last_hmm > 0.65) ? clrDeepSkyBlue : (g_last_hmm < 0.35) ? clrTomato : clrSlateGray;
    color layer_col = (g_layer_allows ? clrSpringGreen : clrTomato);

    CreateLabel(prefix+"T", " SOVEREIGN MASTER V30.0 ", x, y,      10, clrGray);
    CreateLabel(prefix+"S", "System Status: " + g_status,         x, y+18,  10, clrWhite);
    CreateLabel(prefix+"H", "Market Direction: " + DoubleToString(g_last_hmm, 3), x, y+36, 10, hmm_col);
    CreateLabel(prefix+"M", "Master Strength: " + DoubleToString(g_last_strength*100, 1) + "%", x, y+54, 10, str_col);
    CreateLabel(prefix+"V", "Sigma Projected:  " + DoubleToString(g_last_sig_proj*100, 3) + "%", x, y+72, 10, clrDimGray);
    CreateLabel(prefix+"R", "Risk Allocation:  " + DoubleToString(g_risk_percent, 1) + "%",      x, y+90, 10, clrWhite);
    CreateLabel(prefix+"L", "Layer Guard:     " + g_layer_status,                         x, y+108, 10, layer_col);
}

void CreateLabel(string name, string text, int x, int y, int size, color col) {
    if(ObjectFind(0, name) < 0) ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
    ObjectSetString(0, name, OBJPROP_TEXT, text);
    ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
    ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
    ObjectSetInteger(0, name, OBJPROP_COLOR, col);
    ObjectSetInteger(0, name, OBJPROP_FONTSIZE, size);
    ObjectSetString(0, name, OBJPROP_FONT, "Consolas");
    ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
    ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
}

bool IsNewBar() {
    static datetime last_time = 0;
    datetime curr_time = (datetime)SeriesInfoInteger(_Symbol, _Period, SERIES_LASTBAR_DATE);
    if(curr_time != last_time) {
        last_time = curr_time;
        return(true);
    }
    return(false);
}
