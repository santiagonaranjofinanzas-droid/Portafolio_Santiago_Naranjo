import asyncio
from openai import AsyncOpenAI

async def test_llama_json():
    api_key = "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"
    client = AsyncOpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=api_key
    )
    try:
        response = await client.chat.completions.create(
            model="meta/llama-3.1-70b-instruct",
            messages=[{"role": "user", "content": "Respond with a JSON object containing key 'test' and value 'ok'"}],
            response_format={"type": "json_object"},
            max_tokens=50
        )
        print("LLAMA 70b JSON Success!")
        print("Response:", response.choices[0].message.content)
    except Exception as e:
        print("LLAMA 70b JSON Failed:", e)

if __name__ == "__main__":
    asyncio.run(test_llama_json())
