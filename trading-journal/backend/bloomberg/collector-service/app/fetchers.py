import datetime
import math
import os
import requests
import yfinance as yf
import pandas as pd
from typing import List, Dict, Optional
import finnhub
from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

GDELT_BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
NEWSDATA_BASE_URL = "https://newsdata.io/api/1/news"
ALPHAVANTAGE_BASE_URL = "https://www.alphavantage.co/query"
ALTERNATIVE_ME_URL = "https://api.alternative.me/fng/"

def _split_csv(value: str) -> List[str]:
    return [v.strip() for v in value.split(",") if v.strip()]

def _latest_social_entry(entries: list) -> Optional[dict]:
    if not entries:
        return None
    return sorted(entries, key=lambda x: x.get("atTime", ""))[-1]

def fetch_news() -> List[Dict]:
    """Fetches real market news using Finnhub."""
    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:
        print("Aviso: FINNHUB_API_KEY no encontrada. Omitiendo noticias.")
        return []
    
    try:
        finnhub_client = finnhub.Client(api_key=api_key)
        # Traer noticias generales del mercado
        res = finnhub_client.general_news('general', min_id=0)
        
        news_list = []
        # Tomar solo el top 5 para no saturar al LLM
        for item in res[:5]:
            news_list.append({
                "source": item.get('source', 'Finnhub'),
                "feed_kind": "news",
                "title": item.get('headline', ''),
                "content": item.get('summary', ''),
                "published_at": datetime.datetime.fromtimestamp(item.get('datetime', 0)).isoformat(),
                "url": item.get('url', '')
            })
        return news_list
    except Exception as e:
        print(f"Error fetching Finnhub news: {e}")
        return []

def fetch_reddit() -> List[Dict]:
    """Fetches top posts from r/wallstreetbets using Reddit JSON API (Keyless)."""
    try:
        # Se requiere un User-Agent personalizado para que Reddit no bloquee la petición
        headers = {'User-Agent': 'MiroFish-Quant-Bot/1.0 (Contact: admin@mirofish.com)'}
        response = requests.get('https://www.reddit.com/r/wallstreetbets/hot.json?limit=5', headers=headers)
        response.raise_for_status()
        
        data = response.json()
        posts = []
        # Palabras prohibidas para filtrar ruido institucional
        noise_keywords = ["AMA", "personal", "story", "2009", "2008", "journey", "my wife", "my husband", "sold my", "holding for"]
        
        for post in data['data']['children']:
            post_data = post['data']
            title = post_data.get('title', '')
            content = post_data.get('selftext', '')
            
            # Filtro de calidad básica
            if any(kw.lower() in title.lower() for kw in noise_keywords):
                continue
            
            # Ignorar posts muy cortos o sin contenido útil
            if len(content) < 50 and not post_data.get('url'):
                continue

            posts.append({
                "source": "Reddit (r/wallstreetbets)",
                "feed_kind": "social",
                "title": title,
                "content": content[:500],
                "published_at": datetime.datetime.fromtimestamp(post_data.get('created_utc', 0)).isoformat(),
                "url": f"https://reddit.com{post_data.get('permalink', '')}"
            })
        return posts
    except Exception as e:
        print(f"Error fetching Reddit data: {e}")
        return []

def fetch_macro() -> List[Dict]:
    """Fetches macro data using yfinance (Keyless) and optionally FRED."""
    macro_data = []
    
    # 1. Keyless: yfinance (10-Year Treasury Yield)
    try:
        tnx = yf.Ticker("^TNX")
        # Conseguir el precio de cierre más reciente
        hist = tnx.history(period="1d")
        if not hist.empty:
            yield_val = hist['Close'].iloc[-1]
            macro_data.append({
                "source": "Yahoo Finance",
                "feed_kind": "macro",
                "title": "US 10-Year Treasury Yield (^TNX)",
                "content": f"El rendimiento del bono del tesoro a 10 años está en {yield_val:.2f}%.",
                "published_at": datetime.datetime.utcnow().isoformat(),
                "url": "https://finance.yahoo.com/quote/%5ETNX"
            })
    except Exception as e:
        print(f"Error fetching yfinance macro: {e}")

    # 2. Requiere Key: FRED API
    fred_key = os.getenv("FRED_API_KEY")
    if fred_key:
        try:
            # Ejemplo: Tasa de desempleo (UNRATE)
            res = requests.get(f'https://api.stlouisfed.org/fred/series/observations?series_id=UNRATE&api_key={fred_key}&file_type=json&sort_order=desc&limit=1')
            if res.status_code == 200:
                data = res.json()
                obs = data['observations'][0]
                macro_data.append({
                    "source": "FRED API",
                    "feed_kind": "macro",
                    "title": "US Unemployment Rate (UNRATE)",
                    "content": f"La tasa de desempleo reportada más reciente es {obs['value']}%.",
                    "published_at": obs['date'],
                    "url": "https://fred.stlouisfed.org/series/UNRATE"
                })
        except Exception as e:
            print(f"Error fetching FRED macro: {e}")
    else:
        print("Aviso: FRED_API_KEY no encontrada. Omitiendo data macro de la FED.")

    return macro_data

def fetch_finnhub_social() -> List[Dict]:
    """Fetches social sentiment summary from Finnhub."""
    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:
        return []

    tickers = _split_csv(os.getenv("FINNHUB_SOCIAL_TICKERS", "QQQ,SPY,NVDA,AAPL,MSFT"))
    if not tickers:
        return []

    end_date = datetime.datetime.utcnow().date()
    start_date = end_date - datetime.timedelta(days=7)
    finnhub_client = finnhub.Client(api_key=api_key)

    items = []
    for ticker in tickers:
        try:
            res = finnhub_client.social_sentiment(ticker, start_date.isoformat(), end_date.isoformat())
            reddit_entry = _latest_social_entry(res.get("reddit", []))
            twitter_entry = _latest_social_entry(res.get("twitter", []))

            if reddit_entry:
                items.append({
                    "source": "Finnhub Social (Reddit)",
                    "feed_kind": "social",
                    "title": f"{ticker} social sentiment (Reddit)",
                    "content": (
                        f"score={reddit_entry.get('score')}, mentions={reddit_entry.get('mention')}, "
                        f"positive={reddit_entry.get('positiveScore')}, negative={reddit_entry.get('negativeScore')}"
                    ),
                    "published_at": reddit_entry.get("atTime", ""),
                    "url": ""
                })
            if twitter_entry:
                items.append({
                    "source": "Finnhub Social (Twitter)",
                    "feed_kind": "social",
                    "title": f"{ticker} social sentiment (Twitter)",
                    "content": (
                        f"score={twitter_entry.get('score')}, mentions={twitter_entry.get('mention')}, "
                        f"positive={twitter_entry.get('positiveScore')}, negative={twitter_entry.get('negativeScore')}"
                    ),
                    "published_at": twitter_entry.get("atTime", ""),
                    "url": ""
                })
        except Exception as e:
            print(f"Error fetching Finnhub social for {ticker}: {e}")
    return items

def fetch_newsdata() -> List[Dict]:
    """Fetches news from NewsData.io."""
    api_key = os.getenv("NEWSDATA_API_KEY")
    if not api_key:
        return []

    query = os.getenv("NEWSDATA_QUERY", "market OR stocks OR inflation OR fed")
    language = os.getenv("NEWSDATA_LANGUAGE", "en")
    limit = int(os.getenv("NEWSDATA_LIMIT", "10"))

    params = {
        "apikey": api_key,
        "q": query,
        "language": language,
        "size": limit
    }

    try:
        response = requests.get(NEWSDATA_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Error fetching NewsData: {e}")
        return []

    results = []
    for item in data.get("results", [])[:limit]:
        results.append({
            "source": f"NewsData ({item.get('source_id', 'NewsData')})",
            "feed_kind": "news",
            "title": item.get("title", ""),
            "content": item.get("description", ""),
            "published_at": item.get("pubDate", ""),
            "url": item.get("link", "")
        })
    return results

def fetch_gdelt() -> List[Dict]:
    """Fetches global news from GDELT Doc 2.0."""
    query = os.getenv("GDELT_QUERY", "theme:ECON_STOCKMARKET OR theme:ECON_INFLATION OR theme:ECON_INTEREST_RATES")
    timespan = os.getenv("GDELT_TIMESPAN", "24h")
    maxrecords = int(os.getenv("GDELT_MAXRECORDS", "10"))

    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "timespan": timespan,
        "maxrecords": maxrecords
    }

    try:
        response = requests.get(GDELT_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Error fetching GDELT: {e}")
        return []

    results = []
    for item in data.get("articles", [])[:maxrecords]:
        results.append({
            "source": f"GDELT ({item.get('domain', 'gdelt')})",
            "feed_kind": "macro",
            "title": item.get("title", ""),
            "content": item.get("seendate", ""),
            "published_at": item.get("seendate", ""),
            "url": item.get("url", "")
        })
    return results

def fetch_alpha_vantage_sentiment() -> List[Dict]:
    """Fetches news sentiment from Alpha Vantage."""
    api_key = os.getenv("ALPHAVANTAGE_API_KEY")
    if not api_key:
        return []

    tickers = _split_csv(os.getenv("ALPHAVANTAGE_TICKERS", "QQQ,SPY,NVDA,AAPL,MSFT"))
    if not tickers:
        return []

    limit = int(os.getenv("ALPHAVANTAGE_LIMIT", "20"))
    params = {
        "function": "NEWS_SENTIMENT",
        "tickers": ",".join(tickers),
        "apikey": api_key,
        "limit": limit
    }

    try:
        response = requests.get(ALPHAVANTAGE_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Error fetching Alpha Vantage sentiment: {e}")
        return []

    results = []
    for item in data.get("feed", [])[:limit]:
        label = item.get("overall_sentiment_label", "")
        score = item.get("overall_sentiment_score", "")
        summary = item.get("summary", "")
        sentiment_line = f"Sentiment: {label} ({score})" if label or score != "" else ""
        content = summary
        if sentiment_line:
            content = f"{summary}\n{sentiment_line}" if summary else sentiment_line
        results.append({
            "source": f"Alpha Vantage ({item.get('source', 'Alpha Vantage')})",
            "feed_kind": "news",
            "title": item.get("title", ""),
            "content": content,
            "published_at": item.get("time_published", ""),
            "url": item.get("url", "")
        })
    return results

def fetch_fear_greed() -> List[Dict]:
    """Fetches the latest Fear & Greed index from Alternative.me."""
    try:
        response = requests.get(ALTERNATIVE_ME_URL, params={"limit": 1, "format": "json"}, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Error fetching Fear & Greed: {e}")
        return []

    entries = data.get("data", [])
    if not entries:
        return []

    entry = entries[0]
    try:
        ts = int(entry.get("timestamp", "0"))
        published_at = datetime.datetime.utcfromtimestamp(ts).isoformat()
    except (TypeError, ValueError):
        published_at = ""

    value = entry.get("value", "")
    label = entry.get("value_classification", "")
    content = f"value={value}, label={label}" if value or label else ""

    return [{
        "source": "Alternative.me Fear & Greed",
        "feed_kind": "social",
        "title": "Fear & Greed Index",
        "content": content,
        "published_at": published_at,
        "url": "https://alternative.me/crypto/fear-and-greed-index/"
    }]

def fetch_prices() -> Dict[str, float]:
    """Fetches real-time price changes for HMM features with 5-day window for stability."""
    tickers = {
        "OIL": "CL=F",
        "USD": "DX-Y.NYB",
        "GOLD": "GC=F",
        "SP500": "^GSPC",
        "BOND10Y": "^TNX"
    }
    results = {}
    for name, ticker in tickers.items():
        try:
            t = yf.Ticker(ticker)
            # Aumentamos a 5 días para evitar huecos de fin de semana o feriados
            hist = t.history(period="5d")
            if len(hist) >= 2:
                prev_close = hist['Close'].iloc[-2]
                curr_close = hist['Close'].iloc[-1]
                ret = float((curr_close - prev_close) / prev_close)
                results[name] = ret if math.isfinite(ret) else 0.0
            else:
                # Fallback: intentar period="1mo" si 5d falla
                hist = t.history(period="1mo")
                if len(hist) >= 2:
                    prev_close = hist['Close'].iloc[-2]
                    curr_close = hist['Close'].iloc[-1]
                    ret = float((curr_close - prev_close) / prev_close)
                    results[name] = ret if math.isfinite(ret) else 0.0
                else:
                    results[name] = 0.0
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            results[name] = 0.0
    return results

def fetch_historical_returns(days: int = 252) -> Optional[pd.DataFrame]:
    """Fetches historical daily returns for QQQ/GLD for covariance estimation."""
    tickers = ["QQQ", "GLD"]
    period = os.getenv("COV_HISTORY_PERIOD", "1y")
    try:
        hist = yf.download(tickers, period=period, interval="1d", auto_adjust=True, progress=False)
    except Exception as e:
        print(f"Error fetching historical returns: {e}")
        return None

    if hist is None or hist.empty:
        return None

    if isinstance(hist.columns, pd.MultiIndex):
        if "Close" in hist.columns:
            close = hist["Close"]
        elif "Adj Close" in hist.columns:
            close = hist["Adj Close"]
        else:
            return None
    else:
        close = hist

    if close.empty:
        return None

    returns = close.pct_change(fill_method=None).dropna()
    if returns.empty:
        return None

    returns = returns.tail(days)
    returns = returns.rename(columns={"QQQ": "QQQ", "GLD": "GLD"})
    return returns

def fetch_ticker_bar() -> List[Dict]:
    """Fetches real-time price and change for the ticker bar."""
    tickers = {
        "BTC-USD": "BTC-USD",
        "ETH-USD": "ETH-USD",
        "EUR/USD": "EURUSD=X",
        "GBP/USD": "GBPUSD=X",
        "AAPL": "AAPL",
        "MSFT": "MSFT",
        "NVDA": "NVDA",
        "TSLA": "TSLA"
    }
    results = []
    for name, ticker in tickers.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="2d")
            if len(hist) >= 2:
                curr = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2]
                change_pct = ((curr - prev) / prev) * 100
                results.append({
                    "symbol": name,
                    "price": float(curr),
                    "change": float(change_pct)
                })
        except:
            continue
    return results

def fetch_historical_features(period: str = "2y") -> pd.DataFrame:
    """Fetches historical daily returns for all HMM features for calibration."""
    tickers = {
        "OIL": "CL=F",
        "USD": "DX-Y.NYB",
        "GOLD": "GC=F",
        "SP500": "^GSPC",
        "BOND10Y": "^TNX"
    }
    try:
        # Download historical data
        raw_data = yf.download(list(tickers.values()), period=period, interval="1d", auto_adjust=True, progress=False)
        if raw_data.empty:
            return pd.DataFrame()

        # Handle potential MultiIndex columns from yf.download
        if isinstance(raw_data.columns, pd.MultiIndex):
            if "Close" in raw_data.columns:
                close = raw_data["Close"]
            elif "Adj Close" in raw_data.columns:
                close = raw_data["Adj Close"]
            else:
                return pd.DataFrame()
        else:
            close = raw_data

        # Calculate returns
        returns = close.pct_change(fill_method=None).dropna()

        # Rename to internal feature names
        inv_map = {v: k for k, v in tickers.items()}
        returns = returns.rename(columns=inv_map)

        # Ensure all required features are present
        required = ["OIL", "USD", "GOLD", "SP500", "BOND10Y"]
        available = [c for c in required if c in returns.columns]
        
        return returns[available]

    except Exception as e:
        print(f"Error fetching historical features: {e}")
        return pd.DataFrame()

def gather_all_sources() -> List[Dict]:
    """Orchestrates all fetchers."""
    return (
        fetch_news()
        + fetch_reddit()
        + fetch_finnhub_social()
        + fetch_newsdata()
        + fetch_gdelt()
        + fetch_alpha_vantage_sentiment()
        + fetch_fear_greed()
        + fetch_macro()
    )


class SystemicUniverseAdapter:
    TICKERS = {
        "SP500": "^GSPC",
        "NASDAQ": "^NDX",
        "RUSSELL": "IWM",
        "EUROPE": "VGK",
        "JAPAN": "EWJ",
        "EMERGING": "EEM",
        "GOLD": "GC=F",
        "SILVER": "SI=F",
        "OIL": "CL=F",
        "BONDS20Y": "TLT",
        "EURUSD": "EURUSD=X",
        "USDJPY": "JPY=X"
    }
    
    _cache = None
    _cache_time = None
    
    @classmethod
    def fetch_returns(cls, days: int = 120) -> dict:
        import numpy as np
        import hashlib
        
        now = datetime.datetime.now()
        if cls._cache is not None and cls._cache_time and (now - cls._cache_time).total_seconds() < 3600:
            return cls._cache

        print(f"[DATA ADAPTER] Fetching systemic returns EOD for {len(cls.TICKERS)} assets...", flush=True)
        tickers_list = list(cls.TICKERS.values())
        
        try:
            raw = yf.download(tickers_list, period="1y", interval="1d", auto_adjust=True, progress=False)
            if raw.empty:
                raise ValueError("No data returned from yfinance")
                
            if isinstance(raw.columns, pd.MultiIndex):
                close = raw["Close"] if "Close" in raw.columns else (raw["Adj Close"] if "Adj Close" in raw.columns else None)
            else:
                close = raw
                
            if close is None or close.empty:
                raise ValueError("Close prices not found in dataset")
                
            inv_map = {v: k for k, v in cls.TICKERS.items()}
            close = close.rename(columns=inv_map)
            
            for k in cls.TICKERS.keys():
                if k not in close.columns:
                    close[k] = np.nan
            
            close = close[list(cls.TICKERS.keys())]
            returns = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
            total_elements = returns.shape[0] * returns.shape[1]
            nans_count = int(returns.isna().sum().sum())
            pct_missing = (nans_count / total_elements) * 100 if total_elements > 0 else 100.0

            # Do not fabricate or forward-fill returns. Keep only dates with broad
            # cross-asset coverage, then remove assets without enough observations.
            min_assets = max(4, int(len(cls.TICKERS) * 0.75))
            returns = returns.dropna(axis=0, thresh=min_assets)
            minimum_asset_observations = max(30, int(len(returns) * 0.80))
            valid_assets = [c for c in returns.columns if returns[c].notna().sum() >= minimum_asset_observations]
            returns = returns[valid_assets].dropna(axis=0, how="any")
            if len(valid_assets) < 4 or len(returns) < 60:
                raise ValueError(f"Insufficient aligned history: {len(returns)} rows, {len(valid_assets)} assets")
            
            if "USDJPY" in returns.columns:
                returns["USDJPY"] = returns["USDJPY"] * -1.0
                
            df_final = returns.tail(days)
            
            csv_str = df_final.to_csv(index=True)
            dataset_hash = hashlib.sha256(csv_str.encode('utf-8')).hexdigest()
            
            result = {
                "status": "success",
                "df": df_final,
                "dataset_hash": dataset_hash,
                "universe_version": "2.0-systemic-eod",
                "pct_imputed": 0.0,
                "pct_missing_raw": round(pct_missing, 2),
                "cobertura": round((len(valid_assets) / len(cls.TICKERS)) * 100.0, 2),
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "assets": valid_assets,
                "provider": "Yahoo Finance",
                "frequency": "1d",
                "observations": len(df_final),
                "window_start": df_final.index.min().isoformat(),
                "window_end": df_final.index.max().isoformat(),
                "data_status": "fresh"
            }
            cls._cache = result
            cls._cache_time = now
            return result
            
        except Exception as e:
            print(f"[DATA ADAPTER][ERROR] Failed to fetch systemic returns: {e}", flush=True)
            if cls._cache is not None:
                cached = dict(cls._cache)
                cached["status"] = "cached"
                cached["data_status"] = "cached"
                cached["error"] = str(e)
                return cached
            return {
                "status": "error",
                "data_status": "unavailable",
                "error": str(e),
                "dataset_hash": None,
                "universe_version": "2.0-systemic-eod",
                "pct_imputed": None,
                "cobertura": 0.0,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "assets": [],
                "provider": "Yahoo Finance",
                "frequency": "1d",
                "observations": 0
            }
