import asyncio
import redis
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
from app.config import REDIS_HOST, REDIS_PORT, MIROFISH_TRIGGER_PERCENTILE, MAX_FEED_AGE_HOURS
from app.agents.context_agents import MacroAgent, SentimentAgent, RiskAgent
from app.agents.synthesis_agent import SynthesisAgent

logging.basicConfig(level=logging.INFO)

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

SOCIAL_SOURCE_HINTS = ("reddit", "stocktwits", "twitter", "x.com")

def _parse_iso_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        ts = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None

def _parse_feed_payload(feed_data: Union[str, Dict[str, Any], List[Dict[str, Any]]]) -> Tuple[List[Dict[str, Any]], Optional[str], Optional[str]]:
    if feed_data is None:
        return [], None, None
    if isinstance(feed_data, list):
        return feed_data, None, None
    if isinstance(feed_data, dict):
        if "events" in feed_data or "news" in feed_data or "account" in feed_data:
            return [], json.dumps(feed_data, ensure_ascii=False), feed_data.get("generated_at")
        items = feed_data.get("data") if isinstance(feed_data.get("data"), list) else []
        return items, None, feed_data.get("timestamp")
    if not isinstance(feed_data, str):
        return [], None, None
    try:
        payload = json.loads(feed_data)
    except json.JSONDecodeError:
        return [], feed_data, None
    if isinstance(payload, list):
        return payload, None, None
    if isinstance(payload, dict):
        items = payload.get("data") if isinstance(payload.get("data"), list) else []
        return items, None, payload.get("timestamp")
    return [], feed_data, None

def _is_social_item(item: Dict[str, Any]) -> bool:
    if str(item.get("feed_kind", "")).lower() == "social":
        return True
    source = str(item.get("source", "")).lower()
    url = str(item.get("url", "")).lower()
    return any(hint in source or hint in url for hint in SOCIAL_SOURCE_HINTS)

def _format_items(items: List[Dict[str, Any]], max_items: int = 20) -> str:
    lines = []
    for idx, item in enumerate(items[:max_items], start=1):
        source = item.get("source", "")
        title = item.get("title", "")
        content = item.get("content", "")
        published_at = item.get("published_at", "")
        url = item.get("url", "")
        lines.append(f"[{idx}] source: {source}  title: {title}")
        if content:
            lines.append(f"content: {content}")
        if published_at:
            lines.append(f"published_at: {published_at}")
        if url:
            lines.append(f"url: {url}")
    return "\n".join(lines)

async def run_swarm(feed_data: Union[str, Dict[str, Any], List[Dict[str, Any]]]) -> dict:
    macro_agent = MacroAgent()
    sentiment_agent = SentimentAgent()
    risk_agent = RiskAgent()
    synthesis_agent = SynthesisAgent()

    items, raw_text, _ = _parse_feed_payload(feed_data)
    sources_used = len(items)
    if isinstance(feed_data, dict) and ("events" in feed_data or "news" in feed_data):
        sources_used = len(feed_data.get("events", [])) + len(feed_data.get("news", []))

    if raw_text:
        macro_input = raw_text
        sentiment_input = raw_text
        risk_input = raw_text
    else:
        social_items = [item for item in items if _is_social_item(item)]
        macro_items = [item for item in items if not _is_social_item(item)]

        macro_input = _format_items(macro_items) if macro_items else "NO_MACRO_FEED_AVAILABLE"
        sentiment_input = _format_items(social_items) if social_items else "NO_SOCIAL_FEED_AVAILABLE"
        risk_input = _format_items(items) if items else "NO_RISK_FEED_AVAILABLE"

    results = await asyncio.gather(
        macro_agent.run(macro_input),
        sentiment_agent.run(sentiment_input),
        risk_agent.run(risk_input),
        return_exceptions=True
    )

    valid_results = [r for r in results if not isinstance(r, Exception)]
    failed_count = len(results) - len(valid_results)

    if len(valid_results) == 0:
        logging.error("Todos los agentes de contexto fallaron.")
        return None

    macro_out = results[0] if not isinstance(results[0], Exception) else "MACRO_UNAVAILABLE"
    sentiment_out = results[1] if not isinstance(results[1], Exception) else "SENTIMENT_UNAVAILABLE"
    risk_out = results[2] if not isinstance(results[2], Exception) else "RISK_UNAVAILABLE"

    try:
        final_output = await synthesis_agent.run(macro_out, sentiment_out, risk_out, failed_count, sources_used)
        return final_output
    except Exception as e:
        logging.error(f"Error en SynthesisAgent: {e}")
        return None

def check_and_run_cron():
    try:
        stress_prob_str = redis_client.get("quant:stress_prob")
    except redis.exceptions.ConnectionError:
        logging.error("Redis no disponible.")
        return

    if not stress_prob_str:
        logging.info("No quant:stress_prob found in Redis. Skipping.")
        return

    try:
        stress_prob = float(stress_prob_str)
    except (TypeError, ValueError):
        logging.warning("Invalid quant:stress_prob in Redis. Skipping.")
        return
    percentile_proxy = stress_prob * 100
    
    if percentile_proxy >= MIROFISH_TRIGGER_PERCENTILE:
        logging.info(f"Trigger condition met! Stress={percentile_proxy:.1f} >= {MIROFISH_TRIGGER_PERCENTILE}. Starting Swarm...")
        feed_data_str = redis_client.get("processed_feed:latest")
        if not feed_data_str:
            logging.warning("No processed_feed:latest found in Redis. Cannot run swarm.")
            return

        items, raw_text, feed_timestamp = _parse_feed_payload(feed_data_str)
        feed_dt = _parse_iso_timestamp(feed_timestamp)
        if feed_dt:
            age_hours = (datetime.now(timezone.utc) - feed_dt).total_seconds() / 3600
            if age_hours > MAX_FEED_AGE_HOURS:
                logging.warning("Processed feed is stale. Clearing mirofish:latest and skipping run.")
                redis_client.delete("mirofish:latest")
                return
            
        final_output = asyncio.run(run_swarm(items if items else raw_text or feed_data_str))
        
        if final_output:
            redis_client.setex("mirofish:latest", 86400, json.dumps(final_output))
            logging.info("Swarm execution successful. Saved to mirofish:latest")
        else:
            logging.error("Swarm execution failed. Deleting mirofish:latest to trigger NARRATIVE_UNAVAILABLE.")
            redis_client.delete("mirofish:latest")
    else:
        logging.info(f"Condition not met. Stress={percentile_proxy:.1f} < {MIROFISH_TRIGGER_PERCENTILE}.")

if __name__ == "__main__":
    check_and_run_cron()
