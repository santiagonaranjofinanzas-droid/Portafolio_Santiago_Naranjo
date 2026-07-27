import os
import json
from pydantic import ValidationError
from app.llm_client import call_nvidia_api
from app.schemas import NarrativeOutput
from app.config import NVIDIA_MODEL_STRONG, SYNTHESIS_TEMPERATURE, MAX_TOKENS_SYNTHESIS

def _repair_truncated_json(json_str: str) -> str:
    json_str = json_str.strip()
    if not json_str:
        return "{}"
    try:
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError:
        pass

    in_string = False
    escape = False
    brackets = []
    repaired = []
    
    for char in json_str:
        if escape:
            repaired.append(char)
            escape = False
            continue
        if char == '\\':
            repaired.append(char)
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            repaired.append(char)
            continue
            
        if not in_string:
            if char in ('{', '['):
                brackets.append(char)
            elif char in ('}', ']'):
                if brackets:
                    brackets.pop()
        repaired.append(char)
        
    repaired_str = "".join(repaired)
    if in_string:
        repaired_str += '"'
    while brackets:
        open_bracket = brackets.pop()
        if open_bracket == '{':
            repaired_str += '}'
        elif open_bracket == '[':
            repaired_str += ']'
            
    return repaired_str

class SynthesisAgent:
    def __init__(self):
        self.model = NVIDIA_MODEL_STRONG
        self.temperature = SYNTHESIS_TEMPERATURE
        self.max_tokens = MAX_TOKENS_SYNTHESIS
        
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "synthesis_prompt.txt")
        with open(prompt_path, "r", encoding="utf-8") as f:
            self.system_prompt = f.read()

    async def run(self, macro_out: str, sentiment_out: str, risk_out: str, failed_count: int, sources_used: int) -> dict:
        content = (
            f"Macro Analysis:\n{macro_out}\n\n"
            f"Sentiment Analysis:\n{sentiment_out}\n\n"
            f"Risk Analysis:\n{risk_out}\n\n"
            f"Sources Used: {sources_used}"
        )
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": content}
        ]
        
        raw_response = await call_nvidia_api(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"}
        )
        
        try:
            try:
                parsed = json.loads(raw_response)
            except json.JSONDecodeError as jde:
                print(f"[SYNTHESIS] JSON parsing failed, attempting repair. Error: {jde}")
                repaired = _repair_truncated_json(raw_response)
                parsed = json.loads(repaired)
            
            # Defensive validation: convert string to list if LLM returned string instead of list
            for list_field in ["evidence", "account_implications", "invalidation_conditions"]:
                if list_field in parsed and isinstance(parsed[list_field], str):
                    val = parsed[list_field].strip()
                    if "\n" in val:
                        parsed[list_field] = [item.strip("- *").strip() for item in val.split("\n") if item.strip()]
                    else:
                        parsed[list_field] = [val]

            validated = NarrativeOutput(**parsed)
            result = validated.model_dump()
            
            # Incluir los snippets originales para el Dashboard
            result["agent_snippets"] = {
                "macro": macro_out,
                "sentiment": sentiment_out,
                "risk": risk_out
            }
            
            if failed_count > 0:
                result["omega_narr"] = min(1.0, result["omega_narr"] + (0.15 * failed_count))
            result["sources_used"] = sources_used
                
            return result
        except (json.JSONDecodeError, ValidationError) as e:
            import logging
            logging.error(f"[SYNTHESIS_AGENT] Failed to parse or validate LLM response.")
            logging.error(f"[SYNTHESIS_AGENT] Raw response content was:\n{raw_response}")
            raise RuntimeError(f"Synthesis failed validation: {e}")
