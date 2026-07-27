#ifndef H18_SLOW_TREND_CORE_MQH
#define H18_SLOW_TREND_CORE_MQH

#include <Trade/Trade.mqh>
#include "H18_Institutional_Risk.mqh"

// H18 remains research-only.  This engine deliberately refuses live accounts.
// Python is the golden reference; this MQL implementation is independently
// calculated so parity failures expose bugs instead of sharing them.

struct H18HourBar
  {
   datetime time;
   double open;
   double high;
   double low;
   double close;
  };

class CH18SlowTrendEngine
  {
private:
   CTrade   m_trade;
   CInstitutionalRiskGovernor m_risk;
   string   m_system_id;
   string   m_expected_symbol;
   long     m_magic;
   int      m_h1;
   int      m_h2;
   int      m_h3;
   double   m_stop_atr;
   bool     m_trading_enabled;
   double   m_target_annual_vol;
   double   m_max_volume;
   int      m_deviation_points;
   int      m_vol_window;
   int      m_atr_window;
   double   m_entry_threshold;
   double   m_exit_threshold;
   int      m_confirmation_required;
   int      m_minimum_holding_h1;

   bool     m_armed;
   bool     m_logical_position;
   bool     m_execution_stopped;
   int      m_confirmation;
   int      m_holding_h1;
   double   m_virtual_stop;
   datetime m_last_decision_time;
   int      m_signal_handle;
   int      m_deal_handle;
   int      m_risk_handle;
   string   m_signal_file;
   string   m_deal_file;
   string   m_risk_file;
   bool     m_ready;
   bool     m_last_entry_risk_rejected;

   string Key(const string suffix) const
     {
      return StringFormat("H18_%I64d_%I64d_%s",AccountInfoInteger(ACCOUNT_LOGIN),m_magic,suffix);
     }

   void SaveState()
     {
      GlobalVariableSet(Key("ARMED"),m_armed ? 1.0 : 0.0);
      GlobalVariableSet(Key("LOGICAL"),m_logical_position ? 1.0 : 0.0);
      GlobalVariableSet(Key("EXECSTOP"),m_execution_stopped ? 1.0 : 0.0);
      GlobalVariableSet(Key("CONF"),(double)m_confirmation);
      GlobalVariableSet(Key("HOLD"),(double)m_holding_h1);
      GlobalVariableSet(Key("VSTOP"),m_virtual_stop);
      GlobalVariableSet(Key("LAST"),(double)m_last_decision_time);
     }

   bool HasPersistedState() const
     {
      return GlobalVariableCheck(Key("ARMED"))
             && GlobalVariableCheck(Key("LOGICAL"))
             && GlobalVariableCheck(Key("EXECSTOP"))
             && GlobalVariableCheck(Key("CONF"))
             && GlobalVariableCheck(Key("HOLD"))
             && GlobalVariableCheck(Key("VSTOP"))
             && GlobalVariableCheck(Key("LAST"));
     }

   void LoadState()
     {
      m_armed=(GlobalVariableGet(Key("ARMED"))>0.5);
      m_logical_position=(GlobalVariableGet(Key("LOGICAL"))>0.5);
      m_execution_stopped=(GlobalVariableGet(Key("EXECSTOP"))>0.5);
      m_confirmation=(int)GlobalVariableGet(Key("CONF"));
      m_holding_h1=(int)GlobalVariableGet(Key("HOLD"));
      m_virtual_stop=GlobalVariableGet(Key("VSTOP"));
      m_last_decision_time=(datetime)GlobalVariableGet(Key("LAST"));
     }

   int CurrentUtcOffsetSeconds() const
     {
      return (int)(TimeTradeServer()-TimeGMT());
     }

   string TimeText(const datetime value) const
     {
      return TimeToString(value,TIME_DATETIME_SECONDS);
     }

   bool SameHour(const datetime left,const datetime right) const
     {
      MqlDateTime a,b;
      TimeToStruct(left,a);
      TimeToStruct(right,b);
      return a.year==b.year && a.mon==b.mon && a.day==b.day && a.hour==b.hour;
     }

   int MinuteOf(const datetime value) const
     {
      MqlDateTime item;
      TimeToStruct(value,item);
      return item.min;
     }

   bool OpenCsv()
     {
      m_signal_file=StringFormat("H18_%I64d_signals.csv",m_magic);
      m_deal_file=StringFormat("H18_%I64d_deals.csv",m_magic);
      m_signal_handle=FileOpen(m_signal_file,
                               FILE_READFILE_WRITEFILE_CSVFILE_ANSIFILE_SHARE_READFILE_SHARE_WRITEFILE_COMMON,
                               ',');
      if(m_signal_handle==INVALID_HANDLE)
        {
         PrintFormat("H18 FAIL CLOSED: cannot open %s error=%d",m_signal_file,GetLastError());
         return false;
        }
      if(FileSize(m_signal_handle)==0)
         FileWrite(m_signal_handle,"schema_version","system_id","magic","symbol",
                   "decision_server_time","decision_utc_time","utc_offset_seconds",
                   "score","atr_h1","vol_h1","entry_signal","exit_signal","exit_reason",
                   "execution_exit","execution_reason","logical_position","armed","confirmation",
                   "holding_h1","virtual_stop","position_ticket");
      FileSeek(m_signal_handle,0,SEEK_END);

      m_deal_handle=FileOpen(m_deal_file,
                             FILE_READFILE_WRITEFILE_CSVFILE_ANSIFILE_SHARE_READFILE_SHARE_WRITEFILE_COMMON,
                             ',');
      if(m_deal_handle==INVALID_HANDLE)
        {
         PrintFormat("H18 FAIL CLOSED: cannot open %s error=%d",m_deal_file,GetLastError());
         FileClose(m_signal_handle);
         m_signal_handle=INVALID_HANDLE;
         return false;
        }
      if(FileSize(m_deal_handle)==0)
         FileWrite(m_deal_handle,"schema_version","system_id","magic","symbol","deal_ticket",
                   "order_ticket","position_id","server_time","utc_time","utc_offset_seconds",
                   "entry_type","deal_type","volume","price","profit","commission","swap","fee",
                   "deal_reason","comment");
      FileSeek(m_deal_handle,0,SEEK_END);

      m_risk_file=StringFormat("H18_%I64d_risk.csv",m_magic);
      m_risk_handle=FileOpen(m_risk_file,
                             FILE_READFILE_WRITEFILE_CSVFILE_ANSIFILE_SHARE_READFILE_SHARE_WRITEFILE_COMMON,
                             ',');
      if(m_risk_handle==INVALID_HANDLE)
        {
         PrintFormat("H18 FAIL CLOSED: cannot open %s error=%d",m_risk_file,GetLastError());
         FileClose(m_signal_handle);
         FileClose(m_deal_handle);
         m_signal_handle=INVALID_HANDLE;
         m_deal_handle=INVALID_HANDLE;
         return false;
        }
      if(FileSize(m_risk_handle)==0)
         FileWrite(m_risk_handle,"schema_version","system_id","magic","symbol","server_time",
                   "approved","reason","volume","executive_stop","disaster_stop",
                   "requested_risk_cash","authorized_risk_cash","existing_portfolio_risk_cash","throttle",
                   "entry_price","atr_h1","vol_h1","equity","balance","free_margin","margin_level_pct",
                   "day_start_equity","high_water_equity","tick_size","tick_value","volume_min","volume_max",
                   "volume_step","margin_per_lot","maximum_volume");
      FileSeek(m_risk_handle,0,SEEK_END);
      return true;
     }

   void LogRisk(const H18RiskDecision &decision)
     {
      if(m_risk_handle==INVALID_HANDLE) return;
      FileWrite(m_risk_handle,1,m_system_id,m_magic,_Symbol,TimeText(TimeTradeServer()),
                decision.approved ? 1 : 0,decision.reason,DoubleToString(decision.volume,2),
                DoubleToString(decision.executive_stop,_Digits),DoubleToString(decision.disaster_stop,_Digits),
                DoubleToString(decision.requested_risk_cash,2),DoubleToString(decision.authorized_risk_cash,2),
                DoubleToString(decision.existing_risk_cash,2),DoubleToString(decision.throttle,2),
                DoubleToString(decision.entry_price,_Digits),DoubleToString(decision.atr_h1,_Digits),
                DoubleToString(decision.vol_h1,12),DoubleToString(decision.equity,2),DoubleToString(decision.balance,2),
                DoubleToString(decision.free_margin,2),DoubleToString(decision.margin_level_pct,4),
                DoubleToString(decision.day_start_equity,2),DoubleToString(decision.high_water_equity,2),
                DoubleToString(decision.tick_size,8),DoubleToString(decision.tick_value,8),
                DoubleToString(decision.volume_min,4),DoubleToString(decision.volume_max,4),
                DoubleToString(decision.volume_step,4),DoubleToString(decision.margin_per_lot,8),
                DoubleToString(decision.maximum_volume,4));
      FileFlush(m_risk_handle);
     }

   bool GetOwnedPosition(ulong &ticket,int &count) const
     {
      ticket=0;
      count=0;
      for(int i=PositionsTotal()-1;i>=0;i--)
        {
         ulong candidate=PositionGetTicket(i);
         if(candidate==0)
            continue;
         if(PositionGetString(POSITION_SYMBOL)==_Symbol
            && PositionGetInteger(POSITION_MAGIC)==m_magic)
           {
            ticket=candidate;
            count++;
           }
        }
      return count==1;
     }

   bool BuildCompletedHours(H18HourBar &hours[],const int required)
     {
      MqlRates m15[];
      ArraySetAsSeries(m15,true);
      int requested=MathMax(4096,required*12);
      int copied=CopyRates(_Symbol,PERIOD_M15,1,requested,m15);
      if(copied<required*4)
        {
         PrintFormat("H18 waiting for M15 history: copied=%d required~=%d",copied,required*4);
         return false;
        }
      ArrayResize(hours,0);
      int found=0;
      for(int i=0;i<=copied-4 && found<required;i++)
        {
         if(MinuteOf(m15[i].time)!=45
             MinuteOf(m15[i+1].time)!=30
             MinuteOf(m15[i+2].time)!=15
             MinuteOf(m15[i+3].time)!=0)
            continue;
         if(!SameHour(m15[i].time,m15[i+1].time)
             !SameHour(m15[i].time,m15[i+2].time)
             !SameHour(m15[i].time,m15[i+3].time))
            continue;
         ArrayResize(hours,found+1);
         hours[found].time=m15[i].time;
         hours[found].open=m15[i+3].open;
         hours[found].high=MathMax(MathMax(m15[i].high,m15[i+1].high),
                                   MathMax(m15[i+2].high,m15[i+3].high));
         hours[found].low=MathMin(MathMin(m15[i].low,m15[i+1].low),
                                  MathMin(m15[i+2].low,m15[i+3].low));
         hours[found].close=m15[i].close;
         found++;
         i+=3;
        }
      return found>=required;
     }

   double Median3(const double a,const double b,const double c) const
     {
      if((a>=b && a<=c)  (a>=c && a<=b)) return a;
      if((b>=a && b<=c)  (b>=c && b<=a)) return b;
      return c;
     }

   bool CalculateDecision(datetime &decision_time,double &score,double &atr,double &vol,double &decision_close)
     {
      int required=MathMax(MathMax(m_h3,m_vol_window),m_atr_window)+1;
      H18HourBar hours[];
      if(!BuildCompletedHours(hours,required))
         return false;
      if(MinuteOf(hours[0].time)!=45)
         return false;

      double sum=0.0;
      double returns[];
      ArrayResize(returns,m_vol_window);
      for(int i=0;i<m_vol_window;i++)
        {
         if(hours[i].close<=0.0  hours[i+1].close<=0.0)
            return false;
         returns[i]=MathLog(hours[i].close/hours[i+1].close);
         sum+=returns[i];
        }
      double mean=sum/(double)m_vol_window;
      double squared=0.0;
      for(int i=0;i<m_vol_window;i++)
         squared+=(returns[i]-mean)*(returns[i]-mean);
      vol=MathSqrt(squared/(double)(m_vol_window-1));
      if(!MathIsValidNumber(vol)  vol<=0.0)
         return false;

      double s1=MathLog(hours[0].close/hours[m_h1].close)/(vol*MathSqrt((double)m_h1)+1e-12);
      double s2=MathLog(hours[0].close/hours[m_h2].close)/(vol*MathSqrt((double)m_h2)+1e-12);
      double s3=MathLog(hours[0].close/hours[m_h3].close)/(vol*MathSqrt((double)m_h3)+1e-12);
      score=Median3(s1,s2,s3);

      atr=0.0;
      for(int i=0;i<m_atr_window;i++)
        {
         double range=hours[i].high-hours[i].low;
         double high_gap=MathAbs(hours[i].high-hours[i+1].close);
         double low_gap=MathAbs(hours[i].low-hours[i+1].close);
         atr+=MathMax(range,MathMax(high_gap,low_gap));
        }
      atr/=(double)m_atr_window;
      decision_time=hours[0].time;
      decision_close=hours[0].close;
      return MathIsValidNumber(score) && MathIsValidNumber(atr) && atr>0.0;
     }

   bool CloseOwnedPosition(const ulong ticket,const string reason)
     {
      m_trade.SetExpertMagicNumber(m_magic);
      m_trade.SetDeviationInPoints(m_deviation_points);
      bool ok=m_trade.PositionClose(ticket,(ulong)m_deviation_points);
      uint retcode=m_trade.ResultRetcode();
      if(!ok  retcode!=TRADE_RETCODE_DONE)
         PrintFormat("H18 close failed magic=%I64d reason=%s retcode=%u %s",
                     m_magic,reason,retcode,m_trade.ResultRetcodeDescription());
      else
         PrintFormat("H18 close requested magic=%I64d reason=%s",m_magic,reason);
      return ok && retcode==TRADE_RETCODE_DONE;
     }

   bool EnterLong(const double atr,const double vol_h1)
     {
      m_last_entry_risk_rejected=false;
      MqlRates current[];
      ArraySetAsSeries(current,true);
      if(CopyRates(_Symbol,PERIOD_M15,0,1,current)!=1)
         return false;
      if(!m_risk.Acquire())
        {
         Print("H18 RISK REJECT: portfolio risk lock is busy");
         H18RiskDecision busy;
         busy.approved=false; busy.reason="PORTFOLIO_LOCK_BUSY"; busy.volume=0.0;
         busy.executive_stop=0.0; busy.disaster_stop=0.0; busy.requested_risk_cash=0.0;
         busy.authorized_risk_cash=0.0; busy.existing_risk_cash=0.0; busy.throttle=1.0;
         busy.entry_price=0.0; busy.atr_h1=0.0; busy.vol_h1=0.0; busy.equity=0.0;
         busy.balance=0.0; busy.free_margin=0.0; busy.margin_level_pct=0.0;
         busy.day_start_equity=0.0; busy.high_water_equity=0.0; busy.tick_size=0.0;
         busy.tick_value=0.0; busy.volume_min=0.0; busy.volume_max=0.0;
         busy.volume_step=0.0; busy.margin_per_lot=0.0; busy.maximum_volume=m_max_volume;
         LogRisk(busy);
         m_last_entry_risk_rejected=true;
         return false;
        }
      double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
      if(ask<=0.0)
        {
         Print("H18 FAIL CLOSED: invalid ask before risk authorization");
         m_risk.Release();
         return false;
        }
      H18RiskDecision decision=m_risk.AuthorizeLong(ask,atr,vol_h1);
      LogRisk(decision);
      if(!decision.approved)
        {
         PrintFormat("H18 RISK REJECT magic=%I64d reason=%s",m_magic,decision.reason);
         m_last_entry_risk_rejected=true;
         m_risk.Release();
         return false;
        }
      m_virtual_stop=decision.executive_stop;
      m_trade.SetExpertMagicNumber(m_magic);
      m_trade.SetDeviationInPoints(m_deviation_points);
      m_trade.SetTypeFillingBySymbol(_Symbol);
      string comment=StringFormat("H18 %s",m_system_id);
      MqlTradeRequest preflight={};
      MqlTradeCheckResult check={};
      preflight.action=TRADE_ACTION_DEAL;
      preflight.magic=m_magic;
      preflight.symbol=_Symbol;
      preflight.volume=decision.volume;
      preflight.type=ORDER_TYPE_BUY;
      preflight.price=ask;
      preflight.sl=decision.disaster_stop;
      preflight.tp=0.0;
      preflight.deviation=(ulong)m_deviation_points;
      long filling=SymbolInfoInteger(_Symbol,SYMBOL_FILLING_MODE);
      if((filling & SYMBOL_FILLING_FOK)==SYMBOL_FILLING_FOK)
         preflight.type_filling=ORDER_FILLING_FOK;
      else if((filling & SYMBOL_FILLING_IOC)==SYMBOL_FILLING_IOC)
         preflight.type_filling=ORDER_FILLING_IOC;
      else
         preflight.type_filling=ORDER_FILLING_RETURN;
      if(!m_trade.OrderCheck(preflight,check))
        {
         PrintFormat("H18 FAIL CLOSED: OrderCheck failed magic=%I64d retcode=%u comment=%s",
                     m_magic,check.retcode,check.comment);
         m_virtual_stop=0.0;
         m_risk.Release();
         return false;
        }
      bool ok=m_trade.Buy(decision.volume,_Symbol,0.0,decision.disaster_stop,0.0,comment);
      uint retcode=m_trade.ResultRetcode();
      if(!ok  retcode!=TRADE_RETCODE_DONE)
        {
         PrintFormat("H18 entry failed magic=%I64d retcode=%u %s",
                     m_magic,retcode,m_trade.ResultRetcodeDescription());
         m_virtual_stop=0.0;
         m_risk.Release();
         return false;
        }
      ulong ticket=0;
      int count=0;
      bool protected_position=GetOwnedPosition(ticket,count);
      double broker_sl=(protected_position ? PositionGetDouble(POSITION_SL) : 0.0);
      if(!protected_position  broker_sl<=0.0)
        {
         Print("H18 FAIL CLOSED: filled position has no confirmed server-side SL");
         m_risk.Release();
         return false;
        }
      PrintFormat("H18 long filled system=%s magic=%I64d volume=%.2f executive_stop=%.2f disaster_stop=%.2f",
                  m_system_id,m_magic,decision.volume,m_virtual_stop,broker_sl);
      m_risk.Release();
      return true;
     }

   void LogSignal(const datetime decision_time,const double score,const double atr,const double vol,
                  const int entry_signal,const bool exit_signal,const string exit_reason,
                  const bool execution_exit,const string execution_reason,const ulong ticket)
     {
      if(m_signal_handle==INVALID_HANDLE)
         return;
      int offset=CurrentUtcOffsetSeconds();
      datetime utc=decision_time-offset;
      FileWrite(m_signal_handle,1,m_system_id,m_magic,_Symbol,TimeText(decision_time),TimeText(utc),offset,
                DoubleToString(score,12),DoubleToString(atr,_Digits),DoubleToString(vol,12),
                entry_signal,exit_signal ? 1 : 0,exit_reason,execution_exit ? 1 : 0,execution_reason,
                m_logical_position ? 1 : 0,m_armed ? 1 : 0,m_confirmation,
                m_holding_h1,DoubleToString(m_virtual_stop,_Digits),ticket);
      FileFlush(m_signal_handle);
     }

public:
   CH18SlowTrendEngine()
     {
      m_signal_handle=INVALID_HANDLE;
      m_deal_handle=INVALID_HANDLE;
      m_risk_handle=INVALID_HANDLE;
      m_ready=false;
      m_last_entry_risk_rejected=false;
     }

   int Init(const string system_id,const long magic,const int horizon1,const int horizon2,
            const int horizon3,const double stop_atr,const string expected_symbol,
            const bool trading_enabled,const double target_annual_vol,const double max_volume,
            const int deviation_points)
     {
      m_system_id=system_id;
      m_magic=magic;
      m_h1=horizon1;
      m_h2=horizon2;
      m_h3=horizon3;
      m_stop_atr=stop_atr;
      m_expected_symbol=expected_symbol;
      m_trading_enabled=trading_enabled;
      m_target_annual_vol=target_annual_vol;
      m_max_volume=max_volume;
      m_deviation_points=deviation_points;
      m_vol_window=96;
      m_atr_window=32;
      m_entry_threshold=0.35;
      m_exit_threshold=0.0;
      m_confirmation_required=2;
      m_minimum_holding_h1=8;
      m_armed=true;
      m_logical_position=false;
      m_execution_stopped=false;
      m_confirmation=0;
      m_holding_h1=0;
      m_virtual_stop=0.0;
      m_last_decision_time=0;

      if(_Symbol!=m_expected_symbol)
        {
         PrintFormat("H18 FAIL CLOSED: expected %s, chart=%s",m_expected_symbol,_Symbol);
         return INIT_PARAMETERS_INCORRECT;
        }
      if(_Period!=PERIOD_M15)
        {
         Print("H18 FAIL CLOSED: attach EA to M15 chart");
         return INIT_PARAMETERS_INCORRECT;
        }
      bool tester=(bool)MQLInfoInteger(MQL_TESTER);
      long trade_mode=AccountInfoInteger(ACCOUNT_TRADE_MODE);
      if(!tester && trade_mode!=ACCOUNT_TRADE_MODE_DEMO)
        {
         Print("H18 FAIL CLOSED: LIVE accounts are not authorized; demo/tester only");
         return INIT_FAILED;
        }
      long margin_mode=AccountInfoInteger(ACCOUNT_MARGIN_MODE);
      if(!tester && margin_mode!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
        {
         Print("H18 FAIL CLOSED: separate magics on one symbol require a hedging account");
         return INIT_FAILED;
        }
      if(!(m_h1<m_h2 && m_h2<m_h3)  m_stop_atr<=0.0
          m_target_annual_vol<=0.0  m_target_annual_vol>1.0  m_max_volume<=0.0)
         return INIT_PARAMETERS_INCORRECT;

      if(!m_risk.Init(_Symbol,m_magic,m_target_annual_vol,m_max_volume))
        {
         Print("H18 FAIL CLOSED: institutional risk governor initialization failed");
         return INIT_FAILED;
        }

      if(tester)
        {
         GlobalVariableDel(Key("ARMED"));
         GlobalVariableDel(Key("LOGICAL"));
         GlobalVariableDel(Key("EXECSTOP"));
         GlobalVariableDel(Key("CONF"));
         GlobalVariableDel(Key("HOLD"));
         GlobalVariableDel(Key("VSTOP"));
         GlobalVariableDel(Key("LAST"));
        }
      if(HasPersistedState())
         LoadState();
      ulong ticket=0;
      int count=0;
      GetOwnedPosition(ticket,count);
      if(count>1)
        {
         Print("H18 FAIL CLOSED: multiple positions found for same magic");
         return INIT_FAILED;
        }
      if(count==1 && (!HasPersistedState()  m_virtual_stop<=0.0))
        {
         Print("H18 FAIL CLOSED: open position has no persisted virtual stop");
         return INIT_FAILED;
        }
      if(count==1 && PositionGetDouble(POSITION_SL)<=0.0)
        {
         Print("H18 FAIL CLOSED: open position has no server-side disaster stop");
         return INIT_FAILED;
        }
      if(m_trading_enabled)
        {
         bool state_allows_flat=(m_logical_position && m_execution_stopped);
         if((count==1 && !m_logical_position)  (count==0 && m_logical_position && !state_allows_flat))
           {
            Print("H18 FAIL CLOSED: broker position and persisted logical state disagree");
            return INIT_FAILED;
           }
        }
      else if(count!=0)
        {
         Print("H18 FAIL CLOSED: observer mode cannot own an open broker position");
         return INIT_FAILED;
        }
      if(!OpenCsv())
         return INIT_FAILED;
      m_trade.SetAsyncMode(false);
      m_trade.SetExpertMagicNumber(m_magic);
      m_ready=true;
      SaveState();
      PrintFormat("H18 initialized system=%s magic=%I64d horizons=%d/%d/%d stop=%.1fATR demo_only=true",
                  m_system_id,m_magic,m_h1,m_h2,m_h3,m_stop_atr);
      return INIT_SUCCEEDED;
     }

   void Deinit()
     {
      SaveState();
      if(m_signal_handle!=INVALID_HANDLE) FileClose(m_signal_handle);
      if(m_deal_handle!=INVALID_HANDLE) FileClose(m_deal_handle);
      if(m_risk_handle!=INVALID_HANDLE) FileClose(m_risk_handle);
      m_signal_handle=INVALID_HANDLE;
      m_deal_handle=INVALID_HANDLE;
      m_risk_handle=INVALID_HANDLE;
      m_ready=false;
     }

   void OnTick()
     {
      if(!m_ready)
         return;
      if(m_trading_enabled && m_risk.EmergencyFlattenRequired())
        {
         ulong emergency_ticket=0;
         int emergency_count=0;
         bool emergency_position=GetOwnedPosition(emergency_ticket,emergency_count);
         if(emergency_count>1  (emergency_position && !CloseOwnedPosition(emergency_ticket,"drawdown_emergency")))
           {
            Print("H18 FAIL CLOSED: emergency flatten failed");
            m_ready=false;
           }
         else if(emergency_position)
           {
            m_execution_stopped=m_logical_position;
            m_virtual_stop=0.0;
            SaveState();
           }
         return;
        }
      MqlRates latest[];
      ArraySetAsSeries(latest,true);
      if(CopyRates(_Symbol,PERIOD_M15,1,1,latest)!=1)
         return;
      if(MinuteOf(latest[0].time)!=45  latest[0].time==m_last_decision_time)
         return;

      datetime decision_time=0;
      double score=0.0,atr=0.0,vol=0.0,decision_close=0.0;
      if(!CalculateDecision(decision_time,score,atr,vol,decision_close))
         return;
      if(decision_time==m_last_decision_time)
         return;
      m_last_decision_time=decision_time;

      ulong ticket=0;
      int count=0;
      bool has_position=GetOwnedPosition(ticket,count);
      if(count>1)
        {
         Print("H18 FAIL CLOSED: multiple owned positions; disabling engine");
         m_ready=false;
         return;
        }

      int entry_signal=0;
      bool exit_signal=false;
      string exit_reason="";
      bool execution_exit=false;
      string execution_reason="";

      // Golden model state: this block mirrors generate_slow_trend_signals and
      // advances even in observer mode. Broker execution is handled separately.
      if(m_logical_position)
        {
         m_holding_h1++;
         if(m_holding_h1>=m_minimum_holding_h1 && score<=m_exit_threshold)
           {
            exit_signal=true;
            exit_reason="slow_momentum_exit";
            m_logical_position=false;
            m_armed=false;
            m_confirmation=0;
            m_holding_h1=0;
           }
        }
      else
        {
         if(!m_armed && score<=m_exit_threshold)
           {
            m_armed=true;
            m_confirmation=0;
           }
         if(m_armed)
           {
            if(score>=m_entry_threshold) m_confirmation++;
            else m_confirmation=0;
            if(m_confirmation>=m_confirmation_required)
              {
               entry_signal=1;
               m_logical_position=true;
               m_armed=false;
               m_confirmation=0;
               m_holding_h1=0;
              }
           }
        }

      if(m_trading_enabled)
        {
         if(has_position && m_virtual_stop<=0.0)
           {
            Print("H18 FAIL CLOSED: position without virtual stop");
            m_ready=false;
            return;
           }
         bool catastrophe_exit=(has_position && decision_close<=m_virtual_stop);
         execution_exit=(has_position && (catastrophe_exit  exit_signal));
         if(execution_exit)
           {
            execution_reason=catastrophe_exit ? "catastrophe_stop" : exit_reason;
            if(!CloseOwnedPosition(ticket,execution_reason))
              {
               m_ready=false;
               return;
              }
            ticket=0;
            m_virtual_stop=0.0;
            m_execution_stopped=(catastrophe_exit && m_logical_position);
           }
         if(entry_signal==1)
           {
            if(!EnterLong(atr,vol))
              {
               if(m_last_entry_risk_rejected)
                 {
                  Print("H18 model entry was intentionally vetoed by institutional risk");
                  m_execution_stopped=true;
                  m_virtual_stop=0.0;
                 }
               else
                 {
                  Print("H18 FAIL CLOSED: model entered but broker order failed");
                  m_ready=false;
                  return;
                 }
              }
            else
              {
               m_execution_stopped=false;
               GetOwnedPosition(ticket,count);
              }
           }
         if(!has_position && m_logical_position && !m_execution_stopped && entry_signal==0)
           {
            Print("H18 FAIL CLOSED: externally closed or missing broker position");
            m_ready=false;
            return;
           }
         if(exit_signal && !m_logical_position)
            m_execution_stopped=false;
        }
      SaveState();
      LogSignal(decision_time,score,atr,vol,entry_signal,exit_signal,exit_reason,
                execution_exit,execution_reason,ticket);
     }

   void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,
                           const MqlTradeResult &result)
     {
      if(!m_ready  trans.type!=TRADE_TRANSACTION_DEAL_ADD  trans.deal==0)
         return;
      if(!HistoryDealSelect(trans.deal))
         return;
      long deal_magic=HistoryDealGetInteger(trans.deal,DEAL_MAGIC);
      string deal_symbol=HistoryDealGetString(trans.deal,DEAL_SYMBOL);
      if(deal_magic!=m_magic  deal_symbol!=_Symbol)
         return;
      datetime server_time=(datetime)HistoryDealGetInteger(trans.deal,DEAL_TIME);
      int offset=CurrentUtcOffsetSeconds();
      datetime utc=server_time-offset;
      FileWrite(m_deal_handle,1,m_system_id,m_magic,_Symbol,trans.deal,
                (ulong)HistoryDealGetInteger(trans.deal,DEAL_ORDER),
                (ulong)HistoryDealGetInteger(trans.deal,DEAL_POSITION_ID),
                TimeText(server_time),TimeText(utc),offset,
                (int)HistoryDealGetInteger(trans.deal,DEAL_ENTRY),
                (int)HistoryDealGetInteger(trans.deal,DEAL_TYPE),
                DoubleToString(HistoryDealGetDouble(trans.deal,DEAL_VOLUME),2),
                DoubleToString(HistoryDealGetDouble(trans.deal,DEAL_PRICE),_Digits),
                DoubleToString(HistoryDealGetDouble(trans.deal,DEAL_PROFIT),2),
                DoubleToString(HistoryDealGetDouble(trans.deal,DEAL_COMMISSION),2),
                DoubleToString(HistoryDealGetDouble(trans.deal,DEAL_SWAP),2),
                DoubleToString(HistoryDealGetDouble(trans.deal,DEAL_FEE),2),
                (int)HistoryDealGetInteger(trans.deal,DEAL_REASON),
                HistoryDealGetString(trans.deal,DEAL_COMMENT));
      FileFlush(m_deal_handle);
     }
  };

#endif
