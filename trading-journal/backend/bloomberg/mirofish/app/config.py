import os
from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "your_key_here")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6380"))
MIROFISH_TRIGGER_PERCENTILE = int(os.getenv("MIROFISH_TRIGGER_PERCENTILE", "75"))
MAX_FEED_AGE_HOURS = int(os.getenv("MAX_FEED_AGE_HOURS", "4"))

NVIDIA_MODEL_FAST     = "meta/llama-3.1-8b-instruct"
NVIDIA_MODEL_STRONG   = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")
SYNTHESIS_TEMPERATURE = 0.0
CONTEXT_TEMPERATURE   = 0.2
MAX_TOKENS_CONTEXT    = 512
MAX_TOKENS_SYNTHESIS  = 2048
