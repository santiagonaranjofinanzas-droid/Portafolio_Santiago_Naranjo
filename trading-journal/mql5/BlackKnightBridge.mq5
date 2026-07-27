//+------------------------------------------------------------------+
//                                              BlackKnightBridge.mq5 
//                                  Copyright 2026, Black Knight SaaS 
//                                             https://blackknight.ai 
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Black Knight SaaS"
#property link      "https://blackknight.ai"
#property version   "1.21"
#property strict

// ESTO ES UN ASESOR EXPERTO (EA) - NO UN INDICADOR

//--- Input parameters
input string   InpApiUrl         = "https://black-knight-backend.onrender.com/api/v1/ingest/mql5"; // URL del Backend Cloud
input string   InpApiKey         = "MSrsOLPG5JYqaF6ORlbx3YsUnRDhMkoAV-s9_fGQxsI";                                         // API Key Real (Header: X-API-KEY)
input int      InpOrganizationId = 1;                                                             // ID de tu Organización
input bool     InpSyncHistory    = false;                                                         // Sincronizar TODO el historial al iniciar
input bool     InpSendSnapshots  = true;                                                          // Enviar snapshots de cuenta
input int      InpSnapshotEverySeconds = 60;                                                      // Cadencia de snapshot
input int      InpHistoryPollSeconds = 10;                                                        // Re-escanear historial reciente
input int      InpHistoryLookbackMinutes = 180;                                                   // Ventana de rescate para deals cerrados

datetime g_last_history_poll = 0;

//+------------------------------------------------------------------+
// Expert initialization function                                   
//+------------------------------------------------------------------+
int OnInit()
{
   Print("--------------------------------------------------");
   Print(" Black Knight Bridge EA Started!");
   Print(" Target URL: ", InpApiUrl);
   Print(" API Key in memory starts with: ", StringSubstr(InpApiKey, 0, 5), "...");
   Print(" IMPORTANT: If URL or Key is wrong, press F7 and click Reset.");
   Print("--------------------------------------------------");
   
   if(InpSyncHistory)
   {
      Print(" Starting Historical Sync. This may take a moment...");
      SyncHistoricalTrades();
      Print(" Historical Sync Completed.");
   }

   if(InpSendSnapshots)
   {
      EventSetTimer(MathMax(1, MathMin(InpSnapshotEverySeconds, InpHistoryPollSeconds)));
      SendAccountSnapshot();
   }
   else
   {
      EventSetTimer(MathMax(1, InpHistoryPollSeconds));
   }
   
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
// Expert deinitialization function                                 
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("Black Knight Bridge EA Stopped.");
}

void OnTimer()
{
   datetime now_ts = TimeCurrent();
   if(InpHistoryPollSeconds > 0 && (now_ts - g_last_history_poll) >= InpHistoryPollSeconds)
   {
      g_last_history_poll = now_ts;
      SyncRecentClosedTrades();
   }

   if(InpSendSnapshots)
      SendAccountSnapshot();
}

//+------------------------------------------------------------------+
// Trade transaction function                                       
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction& trans,
                        const MqlTradeRequest& request,
                        const MqlTradeResult& result)
{
   // Solo nos interesan los deals (operaciones cerradas/ejecutadas)
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD)
   {
      SendTradeToBackend(trans.deal);
      SyncRecentClosedTrades();
   }
}

void SyncRecentClosedTrades()
{
   datetime end = TimeCurrent();
   datetime start = end - (MathMax(1, InpHistoryLookbackMinutes) * 60);
   if(!HistorySelect(start, end))
   {
      Print("Recent history poll failed. Error: ", GetLastError());
      return;
   }

   int total_deals = HistoryDealsTotal();
   for(int i = 0; i < total_deals; i++)
   {
      ulong deal_ticket = HistoryDealGetTicket(i);
      if(deal_ticket == 0)
         continue;

      long deal_type = HistoryDealGetInteger(deal_ticket, DEAL_TYPE);
      long entry_type = HistoryDealGetInteger(deal_ticket, DEAL_ENTRY);
      if((deal_type == DEAL_TYPE_BUY  deal_type == DEAL_TYPE_SELL) &&
         (entry_type == DEAL_ENTRY_OUT  entry_type == DEAL_ENTRY_INOUT))
      {
         SendTradeToBackend(deal_ticket);
         Sleep(50);
      }
   }
}

//+------------------------------------------------------------------+
// Send trade data to FastAPI backend                               
//+------------------------------------------------------------------+
void SendTradeToBackend(ulong deal_ticket)
{
   // Removemos el if(HistoryDealSelect) para evitar conflictos con la caché de HistorySelect
   string symbol = HistoryDealGetString(deal_ticket, DEAL_SYMBOL);
   long type = HistoryDealGetInteger(deal_ticket, DEAL_TYPE);
   double volume = HistoryDealGetDouble(deal_ticket, DEAL_VOLUME);
   double price = HistoryDealGetDouble(deal_ticket, DEAL_PRICE);
   double profit = HistoryDealGetDouble(deal_ticket, DEAL_PROFIT);
   double commission = HistoryDealGetDouble(deal_ticket, DEAL_COMMISSION);
   double swap = HistoryDealGetDouble(deal_ticket, DEAL_SWAP);
   long magic = HistoryDealGetInteger(deal_ticket, DEAL_MAGIC);
   long reason = HistoryDealGetInteger(deal_ticket, DEAL_REASON);
   long position_id = HistoryDealGetInteger(deal_ticket, DEAL_POSITION_ID);
   datetime time = (datetime)HistoryDealGetInteger(deal_ticket, DEAL_TIME);

   // Extract SL and TP from the Order that triggered this deal
   double sl = 0.0;
   double tp = 0.0;
   long order_ticket = HistoryDealGetInteger(deal_ticket, DEAL_ORDER);
   if(HistoryOrderSelect(order_ticket))
   {
      sl = HistoryOrderGetDouble(order_ticket, ORDER_SL);
      tp = HistoryOrderGetDouble(order_ticket, ORDER_TP);
   }

   // DEAL_ENTRY = 0 (IN), 1 (OUT), 2 (INOUT), etc.
   long entry_type = HistoryDealGetInteger(deal_ticket, DEAL_ENTRY);

   // Fallback position_id si es de balance
   long final_pos_id = (position_id > 0) ? position_id : (long)deal_ticket;

   // Construct JSON con nueva arquitectura
   string json = StringFormat(
      "{\"ticket\": %I64d, \"position_id\": %I64d, \"entry_type\": %d, \"symbol\": \"%s\", \"type\": %d, \"volume\": %.2f, \"price\": %.5f, \"profit\": %.2f, \"commission\": %.2f, \"swap\": %.2f, \"sl\": %.5f, \"tp\": %.5f, \"magic\": %I64d, \"reason\": %d, \"time\": \"%s\", \"organization_id\": %d}",
      deal_ticket, final_pos_id, (int)entry_type, symbol, (int)type, volume, price, profit, commission, swap, sl, tp, magic, (int)reason, TimeToString(time, TIME_DATETIME_SECONDS), InpOrganizationId
   );

   char post[];
   char result[];
   string result_headers;
   StringToCharArray(json, post, 0, StringLen(json));

   string headers = "Content-Type: application/json\r\n";
   headers += "X-API-KEY: " + InpApiKey + "\r\n";

   ResetLastError();
   int req_res = WebRequest("POST", InpApiUrl, headers, 5000, post, result, result_headers);

   if(req_res == -1)
   {
      Print(" Error in WebRequest for Deal ", deal_ticket, ". Error code: ", GetLastError());
   }
   else if(req_res != 200)
   {
      Print(" Failed to ingest deal ", deal_ticket, ". HTTP: ", req_res);
   }
   else
   {
      Print(" Trade ", deal_ticket, " sent to Cloud.");
   }
}

//+------------------------------------------------------------------+
// Send account snapshot to backend                                
//+------------------------------------------------------------------+
void SendAccountSnapshot()
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double margin = AccountInfoDouble(ACCOUNT_MARGIN);
   double margin_free = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   double margin_level = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
   long login = (long)AccountInfoInteger(ACCOUNT_LOGIN);
   string server = AccountInfoString(ACCOUNT_SERVER);
   string currency = AccountInfoString(ACCOUNT_CURRENCY);
   datetime now_ts = TimeCurrent();

   string snapshot_url = InpApiUrl;
   StringReplace(snapshot_url, "/ingest/mql5", "/ingest/trade");
   string json = StringFormat(
      "{\"event_type\":\"account_snapshot\",\"account_login\":%d,\"server_name\":\"%s\","+
      "\"captured_at\":%d,\"balance\":%.2f,\"equity\":%.2f,\"margin\":%.2f,"+
      "\"margin_free\":%.2f,\"margin_level\":%.2f,\"currency\":\"%s\"}",
      login, server, (long)now_ts, balance, equity, margin, margin_free, margin_level, currency
   );

   char post[];
   char result[];
   string result_headers;
   StringToCharArray(json, post, 0, StringLen(json));

   string headers = "Content-Type: application/json\r\n";
   int req_res = WebRequest("POST", snapshot_url, headers, 5000, post, result, result_headers);

   if(req_res == -1)
   {
      Print(" Error sending snapshot. Error code: ", GetLastError());
   }
   else if(req_res != 200)
   {
      Print(" Snapshot rejected. HTTP: ", req_res);
   }
   else
   {
      Print(" Snapshot sent. Balance=", DoubleToString(balance, 2), " Equity=", DoubleToString(equity, 2));
   }
}

//+------------------------------------------------------------------+
// Sync entire account history                                      
//+------------------------------------------------------------------+
void SyncHistoricalTrades()
{
   // 1. Get Synced IDs from Server to "Contrast" and avoid duplicates
   string base_url = InpApiUrl;
   int ingest_pos = StringFind(InpApiUrl, "/ingest");
   if(ingest_pos > 0) base_url = StringSubstr(InpApiUrl, 0, ingest_pos);
   
   string status_url = base_url + "/sync/status/" + IntegerToString(InpOrganizationId);
   
   char post[];
   char result[];
   string result_headers;
   string headers = "X-API-KEY: " + InpApiKey + "\r\n";
   
   Print(" Contrasting local history with Cloud database...");
   ResetLastError();
   int res = WebRequest("GET", status_url, headers, 5000, post, result, result_headers);
   
   string synced_ids = "";
   if(res == 200) 
   {
      synced_ids = CharArrayToString(result);
      Print(" Cloud sync status received. Filtering trades...");
   }
   else 
   {
      Print(" Could not contrast data (Server returned ", res, "). Sending all as fallback.");
   }

   if(HistorySelect(0, TimeCurrent()))
   {
      int total_deals = HistoryDealsTotal();
      int sent_count = 0;
      int skipped_count = 0;
      
      // Limpiar la cadena de IDs para una búsqueda robusta
      string clean_synced = synced_ids;
      StringReplace(clean_synced, " ", "");
      StringReplace(clean_synced, "[", ",");
      StringReplace(clean_synced, "]", ",");
      StringReplace(clean_synced, "{", "");
      StringReplace(clean_synced, "}", "");
      StringReplace(clean_synced, "\"synced_ids\":", "");
      StringReplace(clean_synced, ":", "");
      
      for(int i = 0; i < total_deals; i++)
      {
         ulong deal_ticket = HistoryDealGetTicket(i);
         
         if(deal_ticket == 0)
         {
            Print(" Error getting ticket for index ", i, ". Error: ", GetLastError());
            continue;
         }

         long deal_type = HistoryDealGetInteger(deal_ticket, DEAL_TYPE);
         long pos_id = HistoryDealGetInteger(deal_ticket, DEAL_POSITION_ID);
         
         // Capturar Trading (0,1), Balance (2) y otros ajustes financieros
         if(deal_type >= 0 && deal_type <= 15)
         {
            string search_id = "," + IntegerToString(deal_ticket) + ",";
            
            if(res == 200 && StringFind(clean_synced, search_id) >= 0)
            {
               skipped_count++;
               continue;
            }

            Print("▶ Sending Deal: ", deal_ticket, "  Pos: ", pos_id, "  Type: ", deal_type);
            SendTradeToBackend(deal_ticket);
            sent_count++;
            Sleep(100);
         }
         else 
         {
            Print("ℹ Ignored deal ", deal_ticket, " Type: ", deal_type);
         }
      }
      Print(" Sync Finished: ", sent_count, " sent, ", skipped_count, " already in Cloud, ", total_deals, " total processed.");
   }
   else
   {
      Print(" Failed to load history for Sync. Error: ", GetLastError());
   }
}
