from app.agents.base import BaseAgent
from app.config import NVIDIA_MODEL_STRONG, NVIDIA_MODEL_FAST, CONTEXT_TEMPERATURE, MAX_TOKENS_CONTEXT

class MacroAgent(BaseAgent):
    def __init__(self):
        super().__init__("macro_prompt.txt", NVIDIA_MODEL_STRONG, CONTEXT_TEMPERATURE, MAX_TOKENS_CONTEXT)

class SentimentAgent(BaseAgent):
    def __init__(self):
        super().__init__("sentiment_prompt.txt", NVIDIA_MODEL_FAST, CONTEXT_TEMPERATURE, MAX_TOKENS_CONTEXT)

class RiskAgent(BaseAgent):
    def __init__(self):
        super().__init__("risk_prompt.txt", NVIDIA_MODEL_STRONG, CONTEXT_TEMPERATURE, MAX_TOKENS_CONTEXT)
