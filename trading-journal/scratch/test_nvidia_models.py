import asyncio
from openai import AsyncOpenAI
import os
import sys

async def test_model(model_name):
    print(f"\n--- Testing model: {model_name} ---")
    api_key = "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"
    client = AsyncOpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=api_key
    )
    try:
        # 15s timeout
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": "Hello! Reply with a one-word confirmation."}],
                temperature=0.2,
                max_tokens=10
            ),
            timeout=15.0
        )
        print(f"Success! Response: {response.choices[0].message.content}")
    except asyncio.TimeoutError:
        print("Error: Request timed out!")
    except Exception as e:
        print(f"Error: {e}")

async def main():
    models = [
        "meta/llama-3.1-8b-instruct",
        "meta/llama-3.1-70b-instruct",
        "meta/llama3-8b-instruct",
        "meta/llama3-70b-instruct"
    ]
    for model in models:
        await test_model(model)

if __name__ == "__main__":
    asyncio.run(main())
