import os
import requests
import finnhub
from dotenv import load_dotenv

#Load env from backend/.env
env_path = os.path.join("backend", ".env")
load_dotenv(env_path)

def verify_finnhub():
    key = os.getenv("FINNHUB_API_KEY")
    if not key:
        return "Missing Key"
    try:
        client = finnhub.Client(api_key=key)
        res = client.general_news('general', min_id=0)
        return "SUCCESS" if res else "SUCCESS (Empty Response)"
    except Exception as e:
        return f"FAILED: {e}"

def verify_alpha_vantage():
    key = os.getenv("ALPHAVANTAGE_API_KEY")
    if not key:
        return "Missing Key"
    try:
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=IBM&apikey={key}"
        res = requests.get(url, timeout=10)
        data = res.json()
        if "Global Quote" in data or "Note" in data: # Note might be rate limit
            return "SUCCESS"
        return f"FAILED: {data}"
    except Exception as e:
        return f"FAILED: {e}"

def verify_fred():
    key = os.getenv("FRED_API_KEY")
    if not key:
        return "Missing Key"
    try:
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id=UNRATE&api_key={key}&file_type=json&limit=1"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return "SUCCESS"
        return f"FAILED: Status {res.status_code}"
    except Exception as e:
        return f"FAILED: {e}"

def verify_newsdata():
    key = os.getenv("NEWSDATA_API_KEY")
    if not key:
        return "Missing Key"
    try:
        url = f"https://newsdata.io/api/1/news?apikey={key}&q=market"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return "SUCCESS"
        return f"FAILED: Status {res.status_code}"
    except Exception as e:
        return f"FAILED: {e}"

if __name__ == "__main__":
    print(f"Verifying APIs using {env_path}...")
    print(f"Finnhub: {verify_finnhub()}")
    print(f"AlphaVantage: {verify_alpha_vantage()}")
    print(f"FRED: {verify_fred()}")
    print(f"NewsData: {verify_newsdata()}")
