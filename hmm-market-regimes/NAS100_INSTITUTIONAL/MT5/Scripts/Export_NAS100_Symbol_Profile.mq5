#property script_show_inputs
#property strict

input string InpExpectedSymbol = "NAS100.fs";
input string InpOutputFile = "NAS100_fs_symbol_profile.csv";

void OnStart()
  {
   if(_Symbol != InpExpectedSymbol)
     {
      PrintFormat("FAIL CLOSED: attach this script to %s, current chart is %s", InpExpectedSymbol, _Symbol);
      return;
     }

   MqlTick tick={};
   if(!SymbolInfoTick(_Symbol,tick))
     {
      PrintFormat("SymbolInfoTick failed: %d",GetLastError());
      return;
     }

   double one_point_profit=0.0;
   bool profit_ok=OrderCalcProfit(ORDER_TYPE_BUY,_Symbol,1.0,tick.ask,tick.ask+1.0,one_point_profit);
   int handle=FileOpen(InpOutputFile,FILE_WRITEFILE_CSVFILE_ANSI,',');
   if(handle==INVALID_HANDLE)
     {
      PrintFormat("FileOpen failed: %d",GetLastError());
      return;
     }

   FileWrite(handle,"captured_server_time","broker","symbol","description","digits","point","tick_size",
             "tick_value","tick_value_profit","tick_value_loss","contract_size","volume_min","volume_max",
             "volume_step","stops_level_points","freeze_level_points","spread_points","spread_price",
             "bid","ask","swap_long","swap_short","currency_profit","order_calc_profit_1lot_1price",
             "order_calc_profit_ok");
   FileWrite(handle,TimeToString(TimeCurrent(),TIME_DATETIME_SECONDS),TerminalInfoString(TERMINAL_COMPANY),_Symbol,
             SymbolInfoString(_Symbol,SYMBOL_DESCRIPTION),(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS),
             SymbolInfoDouble(_Symbol,SYMBOL_POINT),SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE),
             SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE),SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE_PROFIT),
             SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE_LOSS),SymbolInfoDouble(_Symbol,SYMBOL_TRADE_CONTRACT_SIZE),
             SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN),SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX),
             SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP),(int)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL),
             (int)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_FREEZE_LEVEL),(int)SymbolInfoInteger(_Symbol,SYMBOL_SPREAD),
             tick.ask-tick.bid,tick.bid,tick.ask,SymbolInfoDouble(_Symbol,SYMBOL_SWAP_LONG),
             SymbolInfoDouble(_Symbol,SYMBOL_SWAP_SHORT),SymbolInfoString(_Symbol,SYMBOL_CURRENCY_PROFIT),
             one_point_profit,profit_ok ? "true" : "false");
   FileClose(handle);
   PrintFormat("Profile exported to MQL5/Files/%s",InpOutputFile);
  }
