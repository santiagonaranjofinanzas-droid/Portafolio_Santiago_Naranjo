import sys
import os

#Inject paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, "backend", ".env"))

from app.macro_service import MacroService

def test_caching():
    print("Testing economic calendar fetch & cache...")
    events = MacroService.fetch_economic_calendar()
    print(f"Fetch completed. Total events fetched: {len(events)}")
    if events:
        print("First 3 parsed events:")
        for ev in events[:3]:
            print(ev)
            
    # Test again (should load from cache)
    print("\nSecond fetch (should read from local disk cache):")
    events_cached = MacroService.fetch_economic_calendar()
    print(f"Fetch completed. Total events from cache: {len(events_cached)}")
    
if __name__ == "__main__":
    test_caching()
