//+------------------------------------------------------------------+
//                                                     TSMOM_EA.mq5 
//                                                  Google DeepMind 
//                                             https://deepmind.com 
//+------------------------------------------------------------------+
#property copyright "Google DeepMind"
#property link      "https://deepmind.com"
#property version   "1.00"
#property strict

// Include standard MQL5 Trade library
#include <Trade\Trade.mqh>

//--- Input parameters
input string   InpServerIP           = "127.0.0.1"; // Python Server IP
input int      InpServerPort         = 5001;        // Python Server Port
input int      InpRebalanceHour      = 22;          // Rebalance hour (22 = 10 PM Server / 3:45 PM EST)
input int      InpRebalanceMin       = 45;          // Rebalance minute (45 = 15:45 EST)
input double   InpRiskFactor         = 1.0;         // Sizing multiplier (Risk Factor)
input int      InpSocketTimeout      = 120000;      // Socket timeout in milliseconds (120 seconds)
input double   InpRebalanceThreshold = 0.0150;      // Rebalance threshold (150 bps)
input ulong    InpMagicNumber        = 30002;       // EA Magic Number

//--- Global variables
CTrade   trade;
datetime last_rebalance_date = 0;

//--- Profitable assets list (26 symbols - Sincronizado v0.9.6)
string profitable_symbols[] = {
   "EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCHF", "USDCAD",
   "SPX500", "NAS100", "DJI30", "GER30", "EU50", "UK100", "JPN225",
   "XAUUSD", "XAGUSD", "Cobre", "Brent", "WTI", "GasNatural", "Cafe", 
   "Azucar", "Trigo", "Maiz", "Soja", "US10Y", "BUND"
};

//+------------------------------------------------------------------+
// Expert initialization function                                   
//+------------------------------------------------------------------+
int OnInit()
{
   PrintFormat("TSMOM EA Initialized. Magic Number: %d", InpMagicNumber);
   PrintFormat("Scheduled Rebalance Time: %02d:%02d daily.", InpRebalanceHour, InpRebalanceMin);
   
   // Set trade parameters
   trade.SetDeviationInPoints(10);
   
   // Set the Magic Number for the trade engine
   trade.SetExpertMagicNumber(InpMagicNumber);
   
   // Set timer to check every 10 seconds
   EventSetTimer(10);
   
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
// Expert deinitialization function                                 
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("TSMOM EA Deinitialized.");
}

//+------------------------------------------------------------------+
// Timer event function                                             
//+------------------------------------------------------------------+
void OnTimer()
{
   MqlDateTime current_time;
   TimeToStruct(TimeLocal(), current_time);
   
   // Do not trade on weekends (Saturday=6, Sunday=0)
   if(current_time.day_of_week == 0  current_time.day_of_week == 6)
      return;
      
   // Check if it is rebalance time and we haven't rebalanced today yet
   if(current_time.hour == InpRebalanceHour && current_time.min == InpRebalanceMin)
   {
      datetime today_date = StringToTime(TimeToString(TimeLocal(), TIME_DATE));
      if(last_rebalance_date < today_date)
      {
         Print("Rebalance window open. Connecting to Python Execution Server...");
         string weights_str = "";
         if(GetWeightsFromServer(InpServerIP, InpServerPort, weights_str))
         {
            Print("Weights received successfully. Executing rebalance...");
            ExecuteRebalance(weights_str);
            last_rebalance_date = today_date;
         }
         else
         {
            Print("Failed to get weights from server. Will retry next tick/timer event.");
         }
      }
   }
}

//+------------------------------------------------------------------+
// Expert tick function                                             
//+------------------------------------------------------------------+
void OnTick()
{
   // OnTimer handles the schedule, but we can also trigger on tick if needed
}

//+------------------------------------------------------------------+
// Connects to Python TCP server and retrieves weights              
//+------------------------------------------------------------------+
bool GetWeightsFromServer(string ip, int port, string &response_str)
{
   // Create socket
   int socket = SocketCreate();
   if(socket == INVALID_HANDLE)
   {
      PrintFormat("SocketCreate failed: %d", GetLastError());
      return false;
   }
   
   // Connect to server
   if(!SocketConnect(socket, ip, port, InpSocketTimeout))
   {
      PrintFormat("SocketConnect to %s:%d failed: %d", ip, port, GetLastError());
      SocketClose(socket);
      return false;
   }
   
   // Send request
   string request = "GET_WEIGHTS\n";
   uchar req_data[];
   StringToCharArray(request, req_data);
   
   int sent = SocketSend(socket, req_data, ArraySize(req_data)-1);
   if(sent <= 0)
   {
      PrintFormat("SocketSend failed: %d", GetLastError());
      SocketClose(socket);
      return false;
   }
   
   // Receive weights
   uchar resp_data[];
   int received = 0;
   datetime start_time = TimeLocal();
   
   while(true)
   {
      // Wait a bit for response
      Sleep(100);
      
      uint size = SocketIsReadable(socket);
      if(size > 0)
      {
         uchar chunk[];
         int res = SocketRead(socket, chunk, size, InpSocketTimeout);
         if(res > 0)
         {
            int old_size = ArraySize(resp_data);
            ArrayResize(resp_data, old_size + res);
            ArrayCopy(resp_data, chunk, old_size, 0, res);
            
            // Check for newline (termination of message)
            if(resp_data[ArraySize(resp_data)-1] == '\n')
            {
               break;
            }
         }
      }
      
      // Timeout check
      if(TimeLocal() - start_time > InpSocketTimeout / 1000)
      {
         Print("Socket receive timeout.");
         SocketClose(socket);
         return false;
      }
   }
   
   response_str = CharArrayToString(resp_data);
   response_str = StringSubstr(response_str, 0, StringLen(response_str)-1); // strip trailing newline
   SocketClose(socket);
   return true;
}

//+------------------------------------------------------------------+
// Translates logical Python symbol names to Axi Pro MT5 symbols     
//+------------------------------------------------------------------+
string GetBrokerSymbol(string symbol)
{
   if(symbol == "EURUSD") return "EURUSD.pro";
   if(symbol == "USDJPY") return "USDJPY.pro";
   if(symbol == "GBPUSD") return "GBPUSD.pro";
   if(symbol == "AUDUSD") return "AUDUSD.pro";
   if(symbol == "USDCHF") return "USDCHF.pro";
   if(symbol == "USDCAD") return "USDCAD.pro";
   if(symbol == "XAUUSD") return "XAUUSD.pro";
   if(symbol == "XAGUSD") return "XAGUSD.pro";
   if(symbol == "SPX500") return "US500";
   if(symbol == "NAS100") return "USTECH";
   if(symbol == "DJI30")  return "US30";
   if(symbol == "GER30")  return "GER40";
   if(symbol == "EU50")   return "EU50";
   if(symbol == "UK100")  return "UK100";
   if(symbol == "JPN225") return "JPN225";
   if(symbol == "Cobre")  return "COPPER.fs";
   if(symbol == "Brent")  return "BRENT.fs";
   if(symbol == "WTI")    return "WTI.fs";
   if(symbol == "GasNatural") return "NATGAS.fs";
   if(symbol == "Cafe")   return "COFFEE.fs";
   if(symbol == "Soja")   return "SOYBEAN.fs";
   if(symbol == "Azucar") return "SUGAR.fs";
   if(symbol == "Trigo")  return "WHEAT.fs";
   if(symbol == "Maiz")   return "CORN.fs";
   if(symbol == "US10Y")  return "US10Y.fs";
   if(symbol == "BUND")   return "BUND.fs";
   return symbol;
}

//+------------------------------------------------------------------+
// Parses weights and rebalances portfolio positions                
//+------------------------------------------------------------------+
void ExecuteRebalance(string weights_str)
{
   string weight_pairs[];
   int num_pairs = StringSplit(weights_str, ';', weight_pairs);
   if(num_pairs <= 0)
   {
      Print("Error: Empty weights string.");
      return;
   }
   
   PrintFormat("Parsed %d asset weights.", num_pairs);
   
   // For each weight pair, parse and rebalance
   for(int i = 0; i < num_pairs; i++)
   {
      string pair_parts[];
      int split_parts = StringSplit(weight_pairs[i], ':', pair_parts);
      if(split_parts == 2)
      {
         string python_symbol = pair_parts[0];
         double weight = StringToDouble(pair_parts[1]) * InpRiskFactor;
         
         // Translate standard logic symbol to broker symbol name
         string broker_symbol = GetBrokerSymbol(python_symbol);
         
         // Only trade if symbol is on our profitable list (using standard logical name)
         if(IsSymbolProfitable(python_symbol))
         {
            RebalanceSymbol(broker_symbol, weight);
         }
         else
         {
            // If it's not on the list, force it to 0 to close any residual positions
            RebalanceSymbol(broker_symbol, 0.0);
         }
      }
   }
   Print("Rebalance cycle completed.");
}

//+------------------------------------------------------------------+
// Helper to check if a symbol is in the profitable list            
//+------------------------------------------------------------------+
bool IsSymbolProfitable(string symbol)
{
   int size = ArraySize(profitable_symbols);
   for(int i = 0; i < size; i++)
   {
      if(profitable_symbols[i] == symbol)
         return true;
   }
   return false;
}

//+------------------------------------------------------------------+
// Gets the net open volume for a symbol (Long is +, Short is -)    
//+------------------------------------------------------------------+
double GetCurrentPositionVolume(string symbol)
{
   double total_vol = 0.0;
   int total_positions = PositionsTotal();
   
   for(int i = total_positions - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == symbol)
      {
         // Verify position belongs to our EA's Magic Number
         if(PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         {
            double volume = PositionGetDouble(POSITION_VOLUME);
            ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
            if(type == POSITION_TYPE_BUY)
               total_vol += volume;
            else if(type == POSITION_TYPE_SELL)
               total_vol -= volume;
         }
      }
   }
   return total_vol;
}

//+------------------------------------------------------------------+
// Closes all positions for a given symbol                          
//+------------------------------------------------------------------+
void CloseAllPositions(string symbol)
{
   int total_positions = PositionsTotal();
   for(int i = total_positions - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == symbol)
      {
         // Only close positions that match our EA's Magic Number
         if(PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         {
            ulong ticket = PositionGetInteger(POSITION_TICKET);
            if(!trade.PositionClose(ticket))
            {
               PrintFormat("Error closing position ticket %d for %s: %d - %s", 
                           ticket, symbol, trade.ResultRetcode(), trade.ResultRetcodeDescription());
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
// Closes partial position volume for a given symbol and type      
//+------------------------------------------------------------------+
void ClosePartialPosition(string symbol, ENUM_POSITION_TYPE pos_type, double volume_to_close)
{
   double remaining_vol = volume_to_close;
   int total_positions = PositionsTotal();
   for(int i = total_positions - 1; i >= 0 && remaining_vol > 1e-6; i--)
   {
      if(PositionGetSymbol(i) == symbol)
      {
         if(PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         {
            ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
            if(type == pos_type)
            {
               ulong ticket = PositionGetInteger(POSITION_TICKET);
               double pos_vol = PositionGetDouble(POSITION_VOLUME);
               double close_vol = MathMin(pos_vol, remaining_vol);
               
               // Round close_vol to lot step to be safe
               double lot_step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
               close_vol = MathRound(close_vol / lot_step) * lot_step;
               
               if(close_vol > 0)
               {
                  if(trade.PositionClose(ticket, close_vol))
                  {
                     remaining_vol -= close_vol;
                  }
                  else
                  {
                     PrintFormat("Error closing partial position for ticket %d: %d", ticket, trade.ResultRetcode());
                     break;
                  }
               }
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
// Rebalances a single symbol to its target weight                  
//+------------------------------------------------------------------+
void RebalanceSymbol(string symbol, double weight)
{
   // Check if symbol exists in Market Watch, if not add it
   if(!SymbolSelect(symbol, true))
   {
      PrintFormat("Symbol %s is not available in MetaTrader 5.", symbol);
      return;
   }
   
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double contract_size = SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   
   // Get current market prices
   double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
   double price = (weight > 0) ? ask : bid;
   
   if(price <= 0  contract_size <= 0)
   {
      PrintFormat("Error reading price or contract size for %s", symbol);
      return;
   }
   
   // --- PARCHE DE CONVERSIÓN MONETARIA UNIVERSAL INSTITUCIONAL ---
   // Exposición de un lote estándar en la moneda de la cuenta utilizando el Tick Value oficial
   double tick_size = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   double tick_value = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   
   if(tick_size <= 0  tick_value <= 0)
   {
      PrintFormat("Error reading tick constraints for symbol: %s", symbol);
      return;
   }
   
   // Exposición real en la divisa base de la cuenta por cada 1.0 lote transaccionado
   double one_lot_account_exposure = price * (tick_value / tick_size);
   
   // Get current net volume and current weight ex-ante
   double current_vol = GetCurrentPositionVolume(symbol);
   double current_weight = (equity > 0.0) ? ((current_vol * one_lot_account_exposure) / equity) : 0.0;
   
   // If target weight is effectively 0, close all positions and exit
   if(MathAbs(weight) < 1e-6)
   {
      if(MathAbs(current_vol) > 0.0)
      {
         PrintFormat("Closing positions for %s. Target weight is 0.0", symbol);
         CloseAllPositions(symbol);
      }
      return;
   }
   
   // Check rebalance threshold (150 bps)
   double weight_diff = MathAbs(weight - current_weight);
   if(weight_diff < InpRebalanceThreshold)
   {
      return; // El cambio de peso está dentro del ruido paramétrico, ignorar rebalanceo
   }
   
   // Calculate target lots based on account currency exposure
   double target_lots = (MathAbs(weight) * equity) / one_lot_account_exposure;
   
   // Get lot step and constraints
   double lot_step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   double min_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   
   // Round target lots to the nearest step allowed by the broker
   target_lots = MathRound(target_lots / lot_step) * lot_step;
   
   // Enforce volume constraints
   if(target_lots > 0 && target_lots < min_lot) target_lots = min_lot;
   if(target_lots > max_lot) target_lots = max_lot;
      
   if(target_lots < min_lot)
   {
      if(MathAbs(current_vol) > 0.0)
      {
         PrintFormat("Closing positions for %s: target lots %f below min lot", symbol, target_lots);
         CloseAllPositions(symbol);
      }
      return;
   }
   
   double target_signed_lots = (weight > 0) ? target_lots : -target_lots;
   
   // --- PARCHE DE CORRECCIÓN LOGICAL DE FLIPS Y ESCALADOS ---
   // Verificar si existe una inversión absoluta de la dirección de la tendencia (Long <-> Short)
   bool sign_flip = (current_vol > 0 && target_signed_lots < 0)  (current_vol < 0 && target_signed_lots > 0);
   
   if(sign_flip)
   {
      // Limpiar la lona por completo para evitar colisiones de órdenes encontradas
      CloseAllPositions(symbol);
      current_vol = 0.0;
   }
   
   // Calcular la diferencia neta real de ajuste
   double diff = target_signed_lots - current_vol;
   double rounded_diff = MathRound(MathAbs(diff) / lot_step) * lot_step;
   
   if(rounded_diff < min_lot)
   {
      return; // No se requiere cambio significativo de lotes
   }
   
   // Configurar el tipo de llenado adaptativo según los permisos del símbolo
   uint execution_mode = (uint)SymbolInfoInteger(symbol, SYMBOL_TRADE_EXEMODE);
   if(execution_mode == SYMBOL_TRADE_EXECUTION_MARKET)
      trade.SetTypeFilling(ORDER_FILLING_IOC);
   else
      trade.SetTypeFilling(ORDER_FILLING_RETURN);
      
   PrintFormat("Executing Clean Rebalance -> %s  Target: %f lots  Current: %f lots  Order Size: %f", 
               symbol, target_signed_lots, current_vol, rounded_diff);
               
   // Envío causal de órdenes al mercado sin destruir la direccionalidad del peso
   if(diff > 0)
   {
      if(current_vol < 0)
      {
         // Reducir posición Corta existente
         ClosePartialPosition(symbol, POSITION_TYPE_SELL, rounded_diff);
      }
      else
      {
         // Incrementar posición Larga
         ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
         if(!trade.Buy(rounded_diff, symbol, ask))
         {
            PrintFormat("Execution error in BUY for %s: Code %d", symbol, trade.ResultRetcode());
         }
      }
   }
   else if(diff < 0)
   {
      if(current_vol > 0)
      {
         // Reducir posición Larga existente
         ClosePartialPosition(symbol, POSITION_TYPE_BUY, rounded_diff);
      }
      else
      {
         // Incrementar posición Corta
         bid = SymbolInfoDouble(symbol, SYMBOL_BID);
         if(!trade.Sell(rounded_diff, symbol, bid))
         {
            PrintFormat("Execution error in SELL for %s: Code %d", symbol, trade.ResultRetcode());
         }
      }
   }
}
