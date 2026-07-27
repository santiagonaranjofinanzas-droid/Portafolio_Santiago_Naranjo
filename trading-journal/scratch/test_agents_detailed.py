import asyncio
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
miro_dir = os.path.join(BASE_DIR, "backend", "bloomberg", "mirofish")
sys.path.insert(0, miro_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(miro_dir, ".env"))

from app.agents.context_agents import MacroAgent, SentimentAgent, RiskAgent
from app.agents.synthesis_agent import SynthesisAgent

async def test_agents():
    feed = "MARKET UPDATE: High volatility in USD/JPY. S&P 500 down 2%. Inflation expectations rising."
    
    print("Initializing agents...")
    macro = MacroAgent()
    sentiment = SentimentAgent()
    risk = RiskAgent()
    synthesis = SynthesisAgent()
    
    print("\n1. Running MacroAgent...")
    try:
        macro_out = await asyncio.wait_for(macro.run(feed), timeout=15)
        print(f"MacroAgent success! Output: {macro_out[:100]}...")
    except Exception as e:
        print(f"MacroAgent FAILED: {e}")
        macro_out = "MACRO_FAILED"

    print("\n2. Running SentimentAgent...")
    try:
        sentiment_out = await asyncio.wait_for(sentiment.run(feed), timeout=15)
        print(f"SentimentAgent success! Output: {sentiment_out[:100]}...")
    except Exception as e:
        print(f"SentimentAgent FAILED: {e}")
        sentiment_out = "SENTIMENT_FAILED"

    print("\n3. Running RiskAgent...")
    try:
        risk_out = await asyncio.wait_for(risk.run(feed), timeout=15)
        print(f"RiskAgent success! Output: {risk_out[:100]}...")
    except Exception as e:
        print(f"RiskAgent FAILED: {e}")
        risk_out = "RISK_FAILED"

    print("\n4. Running SynthesisAgent...")
    try:
        final = await asyncio.wait_for(synthesis.run(macro_out, sentiment_out, risk_out, 0, 1), timeout=15)
        print("SynthesisAgent success! Output:")
        print(final)
    except Exception as e:
        print(f"SynthesisAgent FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(test_agents())
