import asyncio
from openai import AsyncOpenAI
import logging

logging.basicConfig(level=logging.DEBUG)

async def test_macro_direct():
    api_key = "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"
    client = AsyncOpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=api_key
    )
    
    system_prompt = (
        "You are an expert Macroeconomics Analyst.\n"
        "Analyze the following financial news and data feed.\n"
        "Identify key macroeconomic shifts, monetary policy changes (FED), and structural trends.\n"
        "Output a concise summary of the macro landscape and its likely impact on tech (QQQ) and gold (GLD)."
    )
    
    feed_data = "MARKET UPDATE: High volatility in USD/JPY. S&P 500 down 2%. Inflation expectations rising."
    
    print("Calling OpenAI client...")
    try:
        response = await client.chat.completions.create(
            model="meta/llama-3.1-70b-instruct",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Here is the latest feed data:\n\n{feed_data}"}
            ],
            temperature=0.2,
            max_tokens=512
        )
        print("SUCCESS!")
        print("Response:", response.choices[0].message.content)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("FAILED with exception:", e)

if __name__ == "__main__":
    asyncio.run(test_macro_direct())
