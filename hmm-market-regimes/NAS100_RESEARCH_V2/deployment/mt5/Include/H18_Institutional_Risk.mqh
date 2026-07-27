#ifndef H18_INSTITUTIONAL_RISK_MQH
#define H18_INSTITUTIONAL_RISK_MQH

// Independent MQL implementation of H18_RISK_V1_20260714.
// Every missing/invalid broker input rejects risk instead of guessing a value.

struct H18RiskDecision
  {
   bool   approved;
   string reason;
   double volume;
   double executive_stop;
   double disaster_stop;
   double requested_risk_cash;
   double authorized_risk_cash;
   double existing_risk_cash;
   double throttle;
   double entry_price;
   double atr_h1;
   double vol_h1;
   double equity;
   double balance;
   double free_margin;
   double margin_level_pct;
   double day_start_equity;
   double high_water_equity;
   double tick_size;
   double tick_value;
   double volume_min;
   double volume_max;
   double volume_step;
   double margin_per_lot;
   double maximum_volume;
  };

class CInstitutionalRiskGovernor
  {
private:
   string m_symbol;
   long   m_magic;
   double m_portfolio_target_vol;
   double m_max_volume;
   double m_per_sleeve_risk;
   double m_aggregate_risk;
   double m_executive_atr;
   double m_disaster_atr;
   double m_daily_lock;
   double m_dd_throttle;
   double m_dd_lock;
   double m_dd_emergency;
   double m_throttle_multiplier;
   double m_max_margin_fraction;
   double m_min_margin_level;
   bool   m_initialized;

   string SharedKey(const string suffix) const
     {
      return StringFormat("H18_RISK_%I64d_%s_%s",AccountInfoInteger(ACCOUNT_LOGIN),m_symbol,suffix);
     }

   int UtcDay() const
     {
      MqlDateTime value;
      TimeToStruct(TimeGMT(),value);
      return value.year*10000+value.mon*100+value.day;
     }

   bool RefreshAccountState(double &equity,double &day_start,double &high_water,
                            double &daily_loss,double &drawdown)
     {
      equity=AccountInfoDouble(ACCOUNT_EQUITY);
      if(equity<=0.0  !MathIsValidNumber(equity))
         return false;
      string day_key=SharedKey("UTC_DAY");
      string day_equity_key=SharedKey("DAY_EQUITY");
      string high_key=SharedKey("HIGH_WATER");
      int today=UtcDay();
      if(!GlobalVariableCheck(day_key)  (int)GlobalVariableGet(day_key)!=today)
        {
         GlobalVariableSet(day_key,(double)today);
         GlobalVariableSet(day_equity_key,equity);
        }
      if(!GlobalVariableCheck(day_equity_key)  GlobalVariableGet(day_equity_key)<=0.0)
         GlobalVariableSet(day_equity_key,equity);
      if(!GlobalVariableCheck(high_key)  GlobalVariableGet(high_key)<=0.0)
         GlobalVariableSet(high_key,equity);
      high_water=GlobalVariableGet(high_key);
      if(equity>high_water)
        {
         high_water=equity;
         GlobalVariableSet(high_key,high_water);
        }
      day_start=GlobalVariableGet(day_equity_key);
      if(day_start<=0.0  high_water<=0.0)
         return false;
      daily_loss=MathMax(0.0,1.0-equity/day_start);
      drawdown=MathMax(0.0,1.0-equity/high_water);
      return true;
     }

   double RiskPerLot(const double entry,const double stop) const
     {
      double tick_size=SymbolInfoDouble(m_symbol,SYMBOL_TRADE_TICK_SIZE);
      double tick_value=SymbolInfoDouble(m_symbol,SYMBOL_TRADE_TICK_VALUE_LOSS);
      if(tick_value<=0.0)
         tick_value=SymbolInfoDouble(m_symbol,SYMBOL_TRADE_TICK_VALUE);
      if(tick_size<=0.0  tick_value<=0.0  entry<=0.0  stop<=0.0)
         return 0.0;
      return MathAbs(entry-stop)*tick_value/tick_size;
     }

   double ExistingPortfolioRisk(bool &valid) const
     {
      valid=true;
      double total=0.0;
      for(int i=PositionsTotal()-1;i>=0;i--)
        {
         ulong ticket=PositionGetTicket(i);
         if(ticket==0  PositionGetString(POSITION_SYMBOL)!=m_symbol)
            continue;
         long magic=PositionGetInteger(POSITION_MAGIC);
         if(magic!=6001 && magic!=6002)
            continue;
         double volume=PositionGetDouble(POSITION_VOLUME);
         double open=PositionGetDouble(POSITION_PRICE_OPEN);
         double sl=PositionGetDouble(POSITION_SL);
         double per_lot=RiskPerLot(open,sl);
         if(volume<=0.0  sl<=0.0  per_lot<=0.0)
           {
            valid=false;
            return 0.0;
           }
         total+=volume*per_lot;
        }
      return total;
     }

   double FloorSafeVolume(const double raw) const
     {
      double minimum=SymbolInfoDouble(m_symbol,SYMBOL_VOLUME_MIN);
      double maximum=MathMin(SymbolInfoDouble(m_symbol,SYMBOL_VOLUME_MAX),m_max_volume);
      double step=SymbolInfoDouble(m_symbol,SYMBOL_VOLUME_STEP);
      if(raw<minimum  minimum<=0.0  maximum<minimum  step<=0.0)
         return 0.0;
      double result=MathFloor((MathMin(raw,maximum)+1e-12)/step)*step;
      if(result+1e-12<minimum)
         return 0.0;
      int digits=0;
      if(step<1.0) digits=(int)MathCeil(-MathLog10(step));
      return NormalizeDouble(result,digits);
     }

public:
   CInstitutionalRiskGovernor() { m_initialized=false; }

   bool Init(const string symbol,const long magic,const double portfolio_target_vol,
             const double maximum_volume)
     {
      m_symbol=symbol;
      m_magic=magic;
      m_portfolio_target_vol=portfolio_target_vol;
      m_max_volume=maximum_volume;
      m_per_sleeve_risk=0.0025;
      m_aggregate_risk=0.0050;
      m_executive_atr=6.0;
      m_disaster_atr=8.0;
      m_daily_lock=0.010;
      m_dd_throttle=0.050;
      m_dd_lock=0.075;
      m_dd_emergency=0.100;
      m_throttle_multiplier=0.50;
      m_max_margin_fraction=0.20;
      m_min_margin_level=300.0;
      m_initialized=(symbol!="" && (magic==6001  magic==6002)
                     && portfolio_target_vol>0.0 && portfolio_target_vol<=1.0
                     && maximum_volume>0.0);
      if((bool)MQLInfoInteger(MQL_TESTER))
        {
         GlobalVariableDel(SharedKey("UTC_DAY"));
         GlobalVariableDel(SharedKey("DAY_EQUITY"));
         GlobalVariableDel(SharedKey("HIGH_WATER"));
         GlobalVariableDel(SharedKey("LOCK"));
        }
      double equity=0.0,day=0.0,high=0.0,daily=0.0,dd=0.0;
      return m_initialized && RefreshAccountState(equity,day,high,daily,dd);
     }

   bool Acquire()
     {
      if(!m_initialized) return false;
      string key=SharedKey("LOCK");
      if(!GlobalVariableCheck(key)) GlobalVariableSet(key,0.0);
      return GlobalVariableSetOnCondition(key,(double)m_magic,0.0);
     }

   void Release()
     {
      string key=SharedKey("LOCK");
      if(GlobalVariableCheck(key) && (long)GlobalVariableGet(key)==m_magic)
         GlobalVariableSet(key,0.0);
     }

   bool EmergencyFlattenRequired()
     {
      double equity=0.0,day=0.0,high=0.0,daily=0.0,dd=0.0;
      if(!RefreshAccountState(equity,day,high,daily,dd))
         return true;
      return dd>=m_dd_emergency;
     }

   H18RiskDecision AuthorizeLong(const double entry,const double atr_h1,const double vol_h1)
     {
      H18RiskDecision result;
      result.approved=false; result.reason="UNINITIALIZED"; result.volume=0.0;
      result.executive_stop=0.0; result.disaster_stop=0.0;
      result.requested_risk_cash=0.0; result.authorized_risk_cash=0.0;
      result.existing_risk_cash=0.0; result.throttle=1.0;
      result.entry_price=entry; result.atr_h1=atr_h1; result.vol_h1=vol_h1;
      result.equity=0.0; result.balance=AccountInfoDouble(ACCOUNT_BALANCE);
      result.free_margin=AccountInfoDouble(ACCOUNT_MARGIN_FREE);
      result.margin_level_pct=AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
      result.day_start_equity=0.0; result.high_water_equity=0.0;
      result.tick_size=SymbolInfoDouble(m_symbol,SYMBOL_TRADE_TICK_SIZE);
      result.tick_value=SymbolInfoDouble(m_symbol,SYMBOL_TRADE_TICK_VALUE_LOSS);
      if(result.tick_value<=0.0) result.tick_value=SymbolInfoDouble(m_symbol,SYMBOL_TRADE_TICK_VALUE);
      result.volume_min=SymbolInfoDouble(m_symbol,SYMBOL_VOLUME_MIN);
      result.volume_max=SymbolInfoDouble(m_symbol,SYMBOL_VOLUME_MAX);
      result.volume_step=SymbolInfoDouble(m_symbol,SYMBOL_VOLUME_STEP);
      result.margin_per_lot=0.0; result.maximum_volume=m_max_volume;
      if(!m_initialized  entry<=0.0  atr_h1<=0.0  vol_h1<=0.0)
         return result;
      double equity=0.0,day=0.0,high=0.0,daily=0.0,dd=0.0;
      if(!RefreshAccountState(equity,day,high,daily,dd))
        { result.reason="INVALID_ACCOUNT_STATE"; return result; }
      result.equity=equity;
      result.day_start_equity=day;
      result.high_water_equity=high;
      double margin_level=AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
      if(margin_level>0.0 && margin_level<m_min_margin_level)
        { result.reason="MARGIN_LEVEL_LOCK"; return result; }
      if(daily>=m_daily_lock)
        { result.reason="DAILY_LOSS_LOCK"; return result; }
      if(dd>=m_dd_lock)
        { result.reason="DRAWDOWN_ENTRY_LOCK"; return result; }

      result.executive_stop=NormalizeDouble(entry-m_executive_atr*atr_h1,_Digits);
      result.disaster_stop=NormalizeDouble(entry-m_disaster_atr*atr_h1,_Digits);
      if(result.disaster_stop<=0.0  result.disaster_stop>=result.executive_stop)
        { result.reason="INVALID_STOP_GEOMETRY"; return result; }
      double risk_per_lot=RiskPerLot(entry,result.disaster_stop);
      if(risk_per_lot<=0.0)
        { result.reason="INVALID_STOP_RISK"; return result; }
      bool portfolio_valid=false;
      result.existing_risk_cash=ExistingPortfolioRisk(portfolio_valid);
      if(!portfolio_valid)
        { result.reason="UNPROTECTED_PORTFOLIO_POSITION"; return result; }
      result.requested_risk_cash=MathMin(equity*m_per_sleeve_risk,
                                        MathMax(0.0,equity*m_aggregate_risk-result.existing_risk_cash));
      if(result.requested_risk_cash<=0.0)
        { result.reason="AGGREGATE_RISK_LIMIT"; return result; }

      double stop_lot=result.requested_risk_cash/risk_per_lot;
      double tick_size=SymbolInfoDouble(m_symbol,SYMBOL_TRADE_TICK_SIZE);
      double tick_value=result.tick_value;
      if(tick_size<=0.0  tick_value<=0.0)
        { result.reason="INVALID_TICK_SPEC"; return result; }
      double annual_cash_vol=entry*(vol_h1/2.0)*(tick_value/tick_size)*MathSqrt(252.0*26.0);
      double volatility_lot=equity*(m_portfolio_target_vol/2.0)/MathMax(annual_cash_vol,1e-12);
      double margin_one=0.0;
      double ask=SymbolInfoDouble(m_symbol,SYMBOL_ASK);
      if(ask<=0.0  !OrderCalcMargin(ORDER_TYPE_BUY,m_symbol,1.0,ask,margin_one)  margin_one<=0.0)
        { result.reason="MARGIN_CALC_FAILED"; return result; }
      result.margin_per_lot=margin_one;
      double margin_lot=AccountInfoDouble(ACCOUNT_MARGIN_FREE)*m_max_margin_fraction/margin_one;
      result.throttle=(dd>=m_dd_throttle ? m_throttle_multiplier : 1.0);
      double raw=MathMin(MathMin(stop_lot,volatility_lot),MathMin(margin_lot,m_max_volume))*result.throttle;
      result.volume=FloorSafeVolume(raw);
      if(result.volume<=0.0)
        { result.reason="BELOW_MINIMUM_SAFE_VOLUME"; return result; }
      result.authorized_risk_cash=result.volume*risk_per_lot;
      if(result.authorized_risk_cash>result.requested_risk_cash+MathMax(0.01,result.requested_risk_cash*1e-9))
        { result.reason="NORMALIZED_VOLUME_EXCEEDS_RISK"; result.volume=0.0; return result; }
      result.approved=true;
      result.reason="APPROVED";
      return result;
     }
  };

#endif
