#Symbol Mapping for MetaTrader 5 to Portfolio Optimization Proxies
#Institutional-grade proxy mapping layer

SYMBOL_MAP = {
    "XAUUSD": "GLD",
    "GOLD": "GLD",
    "NAS100": "QQQ",
    "US100": "QQQ",
    "USTEC": "QQQ",
    "QQQ": "QQQ",
    "EURUSD": "EURUSD",
    "USDJPY": "USDJPY",
    "JPY=X": "USDJPY",
    "BTCUSD": "BTCUSD",
    "BTC-USD": "BTCUSD"
}

def resolve_proxy(symbol: str) -> str  None:
    if not symbol:
        return None
    
    # Strip suffixes (e.g. XAUUSD.pro -> XAUUSD)
    clean_symbol = symbol.split('.')[0].upper()
    
    # Check direct mapping
    if clean_symbol in SYMBOL_MAP:
        return SYMBOL_MAP[clean_symbol]
        
    # Check partial matches
    for k, v in SYMBOL_MAP.items():
        if k in clean_symbol:
            return v
            
    return None
