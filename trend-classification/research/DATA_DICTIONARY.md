#Data dictionary

##Tick input

 Field  Type  Meaning  Use 
------------
 `timestamp`  UTC-like timestamp (provider timezone must be verified)  Quote event time  causal index 
 `bid`  float  executable sell price  OHLC bid, spread, exits 
 `ask`  float  executable buy price  OHLC ask, spread, exits 
 `last`  float/nullable  last trade where supplied  not used for spot signal 
 `volume`  int/float/nullable  provider tick/trade field  treated only as relative activity 
 `flags`  int/nullable  provider event flags  diagnostics 

##M15 output

Bars are right-labeled and right-closed. At timestamp `t`, every aggregate uses ticks
with timestamps in `(t-15min, t]` only. `mid = (bid + ask) / 2` and
`spread = ask - bid`. Signal generation occurs after the bar close; simulation enters
on a later executable quote/bar.

Core columns: bid/ask/mid OHLC, mean/median/max spread, tick count, first/last tick,
and source symbol. Context assets are backward-asof joined so no future context bar is
visible to XAUUSD.

