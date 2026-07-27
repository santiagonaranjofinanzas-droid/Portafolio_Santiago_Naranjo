import asyncio
from openai import AsyncOpenAI

async def test_json_format():
    api_key = "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"
    client = AsyncOpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=api_key
    )
    model = "meta/llama-3.1-70b-instruct"
    print(f"Testing JSON format on model: {model}")
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You must reply in valid JSON. Format: {\"status\": \"confirmed\"}"},
                {"role": "user", "content": "Hello! Confirm status."}
            ],
            temperature=0.2,
            max_tokens=50,
            response_format={"type": "json_object"}
        )
        print("Success!")
        print("Response:", response.choices[0].message.content)
    except Exception as e:
        print("Failed with exception:", e)

if __name__ == "__main__":
    asyncio.run(test_json_format())
