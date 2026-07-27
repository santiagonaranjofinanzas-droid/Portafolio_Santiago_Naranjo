import os
from app.llm_client import call_nvidia_api

class BaseAgent:
    def __init__(self, prompt_file: str, model: str, temperature: float, max_tokens: int):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", prompt_file)
        with open(prompt_path, "r", encoding="utf-8") as f:
            self.system_prompt = f.read()

    async def run(self, feed_data: str) -> str:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Here is the latest feed data:\n\n{feed_data}"}
        ]
        return await call_nvidia_api(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
