import asyncio
import sys
import os

#Inject paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
miro_dir = os.path.join(BASE_DIR, "backend", "bloomberg", "mirofish")
sys.path.insert(0, miro_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(miro_dir, ".env"))

from app.main import run_swarm

async def main():
    print("Testing run_swarm directly...")
    sample_feed = "MARKET UPDATE: High volatility in USD/JPY. S&P 500 down 2%. Inflation expectations rising."
    try:
        res = await run_swarm(sample_feed)
        print("Swarm Result:")
        print(res)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error executing run_swarm: {e}")

if __name__ == "__main__":
    asyncio.run(main())
