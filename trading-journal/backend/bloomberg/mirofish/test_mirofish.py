import pytest
import json
import fakeredis
from unittest.mock import patch, AsyncMock
from app.main import run_swarm

mock_synthesis_response = json.dumps({
    "R_narr": -0.8,
    "omega_narr": 0.2,
    "dominant_theme": "market_panic",
    "confidence": 0.9,
    "sources_used": 15,
    "reasoning": "High panic due to liquidity squeeze."
})

@pytest.fixture
def mock_redis(monkeypatch):
    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("app.main.redis_client", fake_redis)
    return fake_redis

@pytest.mark.asyncio
@patch("app.agents.context_agents.MacroAgent.run", new_callable=AsyncMock)
@patch("app.agents.context_agents.SentimentAgent.run", new_callable=AsyncMock)
@patch("app.agents.context_agents.RiskAgent.run", new_callable=AsyncMock)
@patch("app.agents.synthesis_agent.call_nvidia_api", new_callable=AsyncMock)
async def test_5_partial_failure(mock_nvidia, mock_risk, mock_sent, mock_macro):
    # Macro falla, los demas bien
    mock_macro.side_effect = Exception("Macro API Timeout")
    mock_sent.return_value = "Sentiment is fearful"
    mock_risk.return_value = "No systemic risks"
    
    mock_nvidia.return_value = mock_synthesis_response
    
    result = await run_swarm("some feed")
    
    assert result is not None
    assert result["R_narr"] == -0.8
    # omega_narr inicial era 0.2, + 0.15 por 1 agente fallido (macro) = 0.35
    assert result["omega_narr"] == pytest.approx(0.35)

@pytest.mark.asyncio
@patch("app.agents.context_agents.MacroAgent.run", new_callable=AsyncMock)
@patch("app.agents.context_agents.SentimentAgent.run", new_callable=AsyncMock)
@patch("app.agents.context_agents.RiskAgent.run", new_callable=AsyncMock)
async def test_all_failed(mock_risk, mock_sent, mock_macro):
    mock_macro.side_effect = Exception("Macro Error")
    mock_sent.side_effect = Exception("Sentiment Error")
    mock_risk.side_effect = Exception("Risk Error")
    
    result = await run_swarm("some feed")
    assert result is None 

@pytest.mark.asyncio
@patch("app.agents.synthesis_agent.call_nvidia_api", new_callable=AsyncMock)
@patch("app.agents.context_agents.MacroAgent.run", new_callable=AsyncMock)
@patch("app.agents.context_agents.SentimentAgent.run", new_callable=AsyncMock)
@patch("app.agents.context_agents.RiskAgent.run", new_callable=AsyncMock)
async def test_synthesis_validation_error(mock_risk, mock_sent, mock_macro, mock_nvidia):
    mock_macro.return_value = "ok"
    mock_sent.return_value = "ok"
    mock_risk.return_value = "ok"
    
    # JSON invalido según Pydantic
    bad_json = json.dumps({"wrong_key": 0.5})
    mock_nvidia.return_value = bad_json
    
    result = await run_swarm("some feed")
    assert result is None
