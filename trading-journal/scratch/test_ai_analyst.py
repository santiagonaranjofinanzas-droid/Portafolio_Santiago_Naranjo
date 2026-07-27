import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from backend.app.ai import AIRequest, _build_messages
from backend.app.database import engine
from sqlmodel import Session

def test_ai():
    print("Testing AI Analyst Context Injection...")
    req = AIRequest(
        prompt="¿Cuál es el estado del mercado actual según el Macro Intel?",
        focus="Macro Intel",
        context={}
    )
    
    # Generate system messages
    messages = _build_messages(req, focus="Macro Intel", mode="chat")
    
    print("\n--- Generated Messages for LLM ---")
    for msg in messages:
        print(f"[{msg['role'].upper()}]")
        print(msg['content'])
        print("-" * 40)

if __name__ == "__main__":
    test_ai()
