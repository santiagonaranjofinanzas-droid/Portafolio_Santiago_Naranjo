import asyncio
import random
from openai import AsyncOpenAI, APIStatusError
from app.config import NVIDIA_API_KEY

client = AsyncOpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

async def call_nvidia_api(model: str, messages: list, temperature: float, max_tokens: int, max_retries=3, response_format=None):
    for attempt in range(max_retries):
        try:
            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            if response_format:
                kwargs["response_format"] = response_format
                
            response = await client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except APIStatusError as e:
            if e.status_code not in RETRYABLE_STATUS_CODES:
                raise # Error irrecuperable (ej. 400, 401)
            if attempt == max_retries - 1:
                raise
            wait = (2 ** attempt) + random.uniform(0, 1)
            await asyncio.sleep(wait)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait = (2 ** attempt) + random.uniform(0, 1)
            await asyncio.sleep(wait)
