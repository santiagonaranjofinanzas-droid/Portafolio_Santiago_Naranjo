//+------------------------------------------------------------------+
//                                     Black_Knight_Quant_Reporter.mq5 
//                             Copyright 2026, Black Knight Quant 
//                                             https://bkquant.ai 
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Black Knight Quant"
#property link      "https://bkquant.ai"
#property version   "5.0" // Critical fix: direction from ENTRY deal, not EXIT deal
#property strict

input bool   InpFullHistory = true;          // Sync entire account history?
input int    InpSyncDays    = 90;            // If not full, how many days back?
input string InpOutboxPath  = "_journal_data/outbox_queue/";  // Local outbox folder (relative to MT5 Data folder)
input string InpCheckpointFile = "_last_ticket.state";         // Stored inside outbox folder
input bool   InpUseCheckpoint = false;       // Persist last exported ticket across restarts?
input int    InpSnapshotEverySeconds = 60;   // Account snapshot cadence
input int    InpHistorySyncEverySeconds = 10;// Closed-trade rescan cadence
input int    InpResyncRecentMinutes = 1440;  // Always replay recent closed trades

long g_last_exported_ticket = 0;
datetime g_last_snapshot_ts = 0;
datetime g_last_history_sync_ts = 0;
bool g_sync_in_progress = false;

long LoadLastExportedTicket()
{
   if(!InpUseCheckpoint)
      return 0;

   string statePath = InpOutboxPath + InpCheckpointFile;
   int f = FileOpen(statePath, FILE_READFILE_TXTFILE_ANSI);
   if(f == INVALID_HANDLE)
      return 0;

   string val = FileReadString(f);
   FileClose(f);
   return (long)StringToInteger(val);
}

bool SaveLastExportedTicket(long ticket)
{
   if(!InpUseCheckpoint)
      return true;

   string statePath = InpOutboxPath + InpCheckpointFile;
   int f = FileOpen(statePath, FILE_WRITEFILE_TXTFILE_ANSI);
   if(f == INVALID_HANDLE)
      return false;

   FileWriteString(f, IntegerToString(ticket));
   FileClose(f);
   return true;
}

//+------------------------------------------------------------------+
int OnInit()
{
   Print("Black Knight Quant: Initializing FILE-BASED OUTBOX BRIDGE v4.1...");
   Print("Outbox path: ", InpOutboxPath);
   Print("Terminal Data Folder: ", TerminalInfoString(TERMINAL_DATA_PATH));

   if(InpUseCheckpoint)
   {
      g_last_exported_ticket = LoadLastExportedTicket();
      if(g_last_exported_ticket > 0)
         Print("Black Knight: Checkpoint loaded. Last exported ticket=", g_last_exported_ticket);
      else
         Print("Black Knight: No checkpoint found. First sync may export historical trades.");
   }
   else
   {
      g_last_exported_ticket = 0;
      Print("Black Knight: Checkpoint disabled. Full history replay will run on EA restart.");
   }
   
   SyncHistory();
   ExportAccountSnapshot(true);
   EventSetTimer(MathMax(1, MathMin(InpSnapshotEverySeconds, InpHistorySyncEverySeconds)));
   Print("Black Knight: EA initialized successfully. Listening for trades...");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) { EventKillTimer(); }
void OnTimer()
{
   datetime now_ts = TimeCurrent();
   if(InpHistorySyncEverySeconds > 0 && (now_ts - g_last_history_sync_ts) >= InpHistorySyncEverySeconds)
   {
      g_last_history_sync_ts = now_ts;
      SyncHistory();
   }
   ExportAccountSnapshot(false);
}

void OnTradeTransaction(const MqlTradeTransaction& trans, const MqlTradeRequest& request, const MqlTradeResult& result)
{
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD) SyncHistory();
}

//+------------------------------------------------------------------+
void SyncHistory()
{
   if(g_sync_in_progress)
      return;

   g_sync_in_progress = true;

   datetime end = TimeCurrent();
   datetime start = 0;
   
   if(!InpFullHistory) start = end - (InpSyncDays * 86400);
   
   if(!HistorySelect(start, end)) 
   {
      Print("Black Knight ERROR: HistorySelect failed.");
      g_sync_in_progress = false;
      return;
   }
   
   int total = HistoryDealsTotal();
   if(total == 0)
   {
      g_sync_in_progress = false;
      return;
   }

   long login = (long)AccountInfoInteger(ACCOUNT_LOGIN);
   string server = AccountInfoString(ACCOUNT_SERVER);
   
   int push_count = 0; 
   for(int i = 0; i < total; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket <= 0) continue;

      long deal_type = HistoryDealGetInteger(ticket, DEAL_TYPE);
      
      // BALANCE EVENTS (Deposits / Withdrawals / Initial Balance)
      if(deal_type == DEAL_TYPE_BALANCE)
      {
         datetime bal_time = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);
         double bal_profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
         
         bool is_recent_bal = (InpResyncRecentMinutes > 0 && (end - bal_time) <= (InpResyncRecentMinutes * 60));
         if((long)ticket <= g_last_exported_ticket && !is_recent_bal) continue;
         
         string bal_dir = (bal_profit >= 0 ? "Deposit" : "Withdrawal");
         string bal_comment = HistoryDealGetString(ticket, DEAL_COMMENT);
         
         string bal_json = StringFormat(
            "{\"position_id\":%I64d,\"deal_ticket\":%I64d,\"account_login\":%I64d,\"server_name\":\"%s\",\"symbol\":\"\",\"entrytime\":%I64d,\"exittime\":%I64d,"
            "\"entryprice\":0,\"exitprice\":0,\"gross_pnl\":%.2f,\"commission\":0,\"swap\":0,\"volume\":0,"
            "\"type_op\":2,\"direction\":\"%s\",\"exit_reason\":0,\"netpnl\":%.2f,\"sl\":0,\"tp\":0,\"risk_price\":0,\"valid_sl\":false,"
            "\"magic_number\":0,\"entry_magic\":0,\"exit_magic\":0,\"deal_comment\":\"%s\"}",
            (long)ticket, (long)ticket, login, server, (long)bal_time, (long)bal_time,
            bal_profit, bal_dir, bal_profit, bal_comment
         );
         
         if(WriteTradeToOutbox(bal_json, (long)ticket, (long)ticket))
         {
            push_count++;
            g_last_exported_ticket = (long)ticket;
            if(InpUseCheckpoint)
               SaveLastExportedTicket(g_last_exported_ticket);
         }
         
         HistorySelect(start, end);
         continue;
      }

      // TRADE EXITS ONLY
      long entry_type = HistoryDealGetInteger(ticket, DEAL_ENTRY);
      if(entry_type != DEAL_ENTRY_OUT && entry_type != DEAL_ENTRY_INOUT) continue;

      datetime exit_time = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);
      bool is_recent_replay = (InpResyncRecentMinutes > 0 && (end - exit_time) <= (InpResyncRecentMinutes * 60));
      if((long)ticket <= g_last_exported_ticket && !is_recent_replay) continue;
      
      long pos_id = HistoryDealGetInteger(ticket, DEAL_POSITION_ID);
      string symbol = HistoryDealGetString(ticket, DEAL_SYMBOL);
      double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
      double commission = HistoryDealGetDouble(ticket, DEAL_COMMISSION);
      double swap = HistoryDealGetDouble(ticket, DEAL_SWAP);
      double volume = HistoryDealGetDouble(ticket, DEAL_VOLUME);
      long type = HistoryDealGetInteger(ticket, DEAL_TYPE); 
      long reason = HistoryDealGetInteger(ticket, DEAL_REASON);
      double exit_price = HistoryDealGetDouble(ticket, DEAL_PRICE);

      double export_gross = profit;
      double export_commission = commission;
      double export_swap = swap;
      double export_volume = volume;
      double export_net = profit + commission + swap;
      
      double entry_price = 0;
      datetime entry_time = 0;
      double sl = 0;
      long entry_magic = 0;
      long entry_deal_type = -1;  // Will hold DEAL_TYPE_BUY or DEAL_TYPE_SELL from the ENTRY deal
      
      string partials_json = "[]";
      if(HistorySelectByPosition(pos_id))
      {
         int p_total = HistoryDealsTotal();
         double cumulative_gross = 0;
         double cumulative_commission = 0;
         double cumulative_swap = 0;
         double cumulative_closed_volume = 0;
         double cumulative_entry_volume = 0;
         double weighted_entry_sum = 0;
         double weighted_exit_sum = 0;

         partials_json = "[";
         bool first_partial = true;

         for(int j=0; j<p_total; j++)
         {
            ulong p_ticket = HistoryDealGetTicket(j);
            long p_type = HistoryDealGetInteger(p_ticket, DEAL_TYPE);
            if(p_type != DEAL_TYPE_BUY && p_type != DEAL_TYPE_SELL)
               continue;

            long p_entry = HistoryDealGetInteger(p_ticket, DEAL_ENTRY);
            cumulative_gross += HistoryDealGetDouble(p_ticket, DEAL_PROFIT);
            cumulative_commission += HistoryDealGetDouble(p_ticket, DEAL_COMMISSION);
            cumulative_swap += HistoryDealGetDouble(p_ticket, DEAL_SWAP);

            if(p_entry == DEAL_ENTRY_OUT  p_entry == DEAL_ENTRY_INOUT)
            {
               double cl_vol = HistoryDealGetDouble(p_ticket, DEAL_VOLUME);
               double cl_price = HistoryDealGetDouble(p_ticket, DEAL_PRICE);
               cumulative_closed_volume += cl_vol;
               weighted_exit_sum += (cl_price * cl_vol);

               // Extract details for partial exit
               double p_profit = HistoryDealGetDouble(p_ticket, DEAL_PROFIT);
               double p_comm = HistoryDealGetDouble(p_ticket, DEAL_COMMISSION);
               datetime p_time = (datetime)HistoryDealGetInteger(p_ticket, DEAL_TIME);

               // Format date/time to ISO 8601 string: YYYY-MM-DDTHH:MM:SSZ
               string p_time_str = TimeToString(p_time, TIME_DATETIME_SECONDS);
               string year = StringSubstr(p_time_str, 0, 4);
               string month = StringSubstr(p_time_str, 5, 2);
               string day = StringSubstr(p_time_str, 8, 2);
               string time_part = StringSubstr(p_time_str, 11, 8);
               string iso_time = year + "-" + month + "-" + day + "T" + time_part + "Z";

               string p_item = StringFormat(
                  "%s{\"ticket\":%I64d,\"volume\":%.2f,\"price\":%.5f,\"commission\":%.2f,\"profit\":%.2f,\"time\":\"%s\"}",
                  (first_partial ? "" : ","), (long)p_ticket, cl_vol, cl_price, p_comm, p_profit, iso_time
               );
               partials_json += p_item;
               first_partial = false;
            }

            if(p_entry == DEAL_ENTRY_IN)
            {
               double ent_vol = HistoryDealGetDouble(p_ticket, DEAL_VOLUME);
               double ent_price = HistoryDealGetDouble(p_ticket, DEAL_PRICE);
               cumulative_entry_volume += ent_vol;
               weighted_entry_sum += (ent_price * ent_vol);
               
               if(entry_time == 0)
               {
                  entry_time = (datetime)HistoryDealGetInteger(p_ticket, DEAL_TIME);
                  entry_magic = HistoryDealGetInteger(p_ticket, DEAL_MAGIC);
               }
               // Capture the deal type of the FIRST entry deal — this IS the position direction
               if(entry_deal_type == -1)
                  entry_deal_type = p_type;  // DEAL_TYPE_BUY=0 or DEAL_TYPE_SELL=1
            }
         }
         partials_json += "]";

         export_gross = cumulative_gross;
         export_commission = cumulative_commission;
         export_swap = cumulative_swap;
         export_net = export_gross + export_commission + export_swap;
         if(cumulative_closed_volume > 0)
         {
            export_volume = cumulative_closed_volume;
            exit_price = weighted_exit_sum / cumulative_closed_volume;
         }
         if(cumulative_entry_volume > 0)
         {
            entry_price = weighted_entry_sum / cumulative_entry_volume;
         }
         
         for(int k=HistoryOrdersTotal()-1; k>=0; k--)
         {
            ulong o_ticket = HistoryOrderGetTicket(k);
            if(HistoryOrderGetInteger(o_ticket, ORDER_POSITION_ID) == pos_id)
            {
               sl = HistoryOrderGetDouble(o_ticket, ORDER_SL);
               if(sl > 0) break;
            }
         }
      }
      
      // Fallback: if no ENTRY_IN deal was found, infer from the EXIT deal (inverted)
      if(entry_deal_type == -1)
         entry_deal_type = (type == DEAL_TYPE_SELL ? DEAL_TYPE_BUY : DEAL_TYPE_SELL);
      
      // POSITION direction comes from the ENTRY deal type, NOT the exit deal
      // DEAL_TYPE_BUY=0 means position is Buy (type_op=0)
      // DEAL_TYPE_SELL=1 means position is Sell (type_op=1)
      int type_op = (entry_deal_type == DEAL_TYPE_BUY ? 0 : 1);
      string dir_str = (type_op == 0 ? "Buy" : "Sell");
      long exit_magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
      long magic = (entry_magic != 0 ? entry_magic : exit_magic);
      
      // Unix timestamps for outbox format
      long entry_unix = (long)entry_time;
      long exit_unix = (long)exit_time;
      
      string json = StringFormat(
         "{\"position_id\":%I64d,\"deal_ticket\":%I64d,\"account_login\":%I64d,\"server_name\":\"%s\",\"symbol\":\"%s\",\"entrytime\":%I64d,\"exittime\":%I64d,"
         "\"entryprice\":%.5f,\"exitprice\":%.5f,\"gross_pnl\":%.2f,\"commission\":%.2f,"
         "\"swap\":%.2f,\"volume\":%.2f,\"type_op\":%d,\"direction\":\"%s\","
         "\"exit_reason\":%I64d,\"netpnl\":%.2f,\"sl\":%.5f,\"risk_price\":%.5f,\"valid_sl\":%s,"
         "\"magic_number\":%I64d,\"entry_magic\":%I64d,\"exit_magic\":%I64d,\"partials\":%s}",
         pos_id, ticket, login, server, symbol, entry_unix, exit_unix,
         entry_price, exit_price, export_gross, export_commission, export_swap, export_volume, 
         type_op, dir_str,
         reason, export_net, sl, MathAbs(entry_price - sl), (sl > 0 ? "true" : "false"),
         magic, entry_magic, exit_magic, partials_json
      );
      
      if(WriteTradeToOutbox(json, pos_id, (long)ticket))
      {
         push_count++;
         g_last_exported_ticket = (long)ticket;
         if(InpUseCheckpoint)
            SaveLastExportedTicket(g_last_exported_ticket);
      }
      
      // CRITICAL FIX: Restore global history cache wiped by HistorySelectByPosition
      HistorySelect(start, end);
   }
   
   if(push_count > 0) Print("Black Knight: SUCCESS! Exported ", push_count, " trades to outbox folder (", InpOutboxPath, ")");
   g_sync_in_progress = false;
}


//+------------------------------------------------------------------+
bool WriteTradeToOutbox(string json, long pos_id, long deal_ticket)
{
   // Deal ticket makes the filename idempotent and prevents same-second overwrites.
   string filename = InpOutboxPath + "trade_" + IntegerToString(pos_id) + "_" + IntegerToString(deal_ticket) + ".json";
   
   int file = FileOpen(filename, FILE_WRITEFILE_ANSI);
   if(file == INVALID_HANDLE)
   {
      int err = GetLastError();
      Print("Black Knight FILE ERROR: Cannot write to ", filename, " (Error ", err, ")");
      Print("Make sure the folder exists in: ", TerminalInfoString(TERMINAL_DATA_PATH), "/", InpOutboxPath);
      return false;
   }
   
   // Write JSON to file
   FileWriteString(file, json);
   FileClose(file);
   
   Print("Black Knight: Trade ", pos_id, " deal ", deal_ticket, " written to outbox: ", filename);
   return true;
}

bool ExportAccountSnapshot(bool force)
{
   datetime now_ts = TimeCurrent();
   if(!force && InpSnapshotEverySeconds > 0 && (now_ts - g_last_snapshot_ts) < InpSnapshotEverySeconds)
      return true;

   long login = (long)AccountInfoInteger(ACCOUNT_LOGIN);
   string server = AccountInfoString(ACCOUNT_SERVER);
   string currency = AccountInfoString(ACCOUNT_CURRENCY);
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double margin = AccountInfoDouble(ACCOUNT_MARGIN);
   double margin_free = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   double margin_level = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);

   string json = StringFormat(
      "{\"event_type\":\"account_snapshot\",\"account_login\":%I64d,\"server_name\":\"%s\","
      "\"captured_at\":%I64d,\"balance\":%.2f,\"equity\":%.2f,\"margin\":%.2f,"
      "\"margin_free\":%.2f,\"margin_level\":%.2f,\"currency\":\"%s\"}",
      login, server, (long)now_ts, balance, equity, margin, margin_free, margin_level, currency
   );

   string filename = InpOutboxPath + "snapshot_" + IntegerToString((int)login) + "_" + IntegerToString((int)now_ts) + ".json";
   int file = FileOpen(filename, FILE_WRITEFILE_ANSI);
   if(file == INVALID_HANDLE)
   {
      int err = GetLastError();
      Print("Black Knight FILE ERROR: Cannot write account snapshot to ", filename, " (Error ", err, ")");
      return false;
   }

   FileWriteString(file, json);
   FileClose(file);
   g_last_snapshot_ts = now_ts;
   Print("Black Knight: Account snapshot written. balance=", DoubleToString(balance, 2), " equity=", DoubleToString(equity, 2));
   return true;
}
//+------------------------------------------------------------------+
