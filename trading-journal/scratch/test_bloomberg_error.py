import sys
import os
import asyncio

#Add the bloomberg path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "bloomberg"))

import master_orchestrator

async def test():
    print("Testing run_cycle from master_orchestrator...")
    # Mock requests.post to print what it would send
    import requests
    original_post = requests.post
    def mock_post(url, *args, **kwargs):
        print(f"requests.post called for URL: {url}")
        print(f"Payload: {kwargs.get('json')}")
        # Call original or return a dummy response
        class DummyResponse:
            status_code = 200
            def json(self): return {"status": "success"}
        return DummyResponse()
    requests.post = mock_post

    await master_orchestrator.run_cycle()

if __name__ == "__main__":
    asyncio.run(test())
