#property strict
#property version "1.10"
#property description "H18 TREND_11 with shared institutional risk - DEMO/TESTER ONLY"

#include "..\\Include\\H18_SlowTrend_Core.mqh"

input string InpExpectedSymbol="NAS100.fs";
input bool   InpTradingEnabled=false;
input double InpPortfolioTargetAnnualVolatility=0.10;
input double InpMaximumVolume=10.0;
input int    InpDeviationPoints=50;

const long H18_MAGIC=6002;
CH18SlowTrendEngine engine;

int OnInit()
  {
   return engine.Init("TREND_11_ULTRASLOW_LONG",H18_MAGIC,24,48,96,6.0,
                      InpExpectedSymbol,InpTradingEnabled,InpPortfolioTargetAnnualVolatility,
                      InpMaximumVolume,InpDeviationPoints);
  }

void OnDeinit(const int reason) { engine.Deinit(); }
void OnTick() { engine.OnTick(); }
void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  { engine.OnTradeTransaction(trans,request,result); }
