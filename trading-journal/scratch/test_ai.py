import os
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv("backend/.env")

async def test_nvidia():
    api_key = os.getenv("NVIDIA_API_KEY")
    model = os.getenv("NVIDIA_MODEL")
    print(f"Testing with model: {model}")
    
    client = AsyncOpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=api_key
    )
    
    try:
        completion = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Hola, responde con 'OK' si puedes leer esto."}],
            max_tokens=10
        )
        print(f"Response: {completion.choices[0].message.content}")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_nvidia())
