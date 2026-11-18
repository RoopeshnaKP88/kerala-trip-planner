"""Chat framework: Agno. A single Agent with a Pydantic output schema (Gemini)."""
from functools import lru_cache

from .agent_core import INSTRUCTIONS, ChatDecision, coerce_decision, plan_json
from .config import settings
from .models import TripState


@lru_cache(maxsize=1)
def _agent():
    from agno.agent import Agent
    from agno.models.google import Gemini

    model = Gemini(id=settings.gemini_model, api_key=settings.gemini_api_key)
    return Agent(model=model, instructions=INSTRUCTIONS, output_schema=ChatDecision)


async def decide(trip: TripState, message: str) -> ChatDecision:
    run = await _agent().arun(f"CURRENT PLAN:\n{plan_json(trip)}\n\nUSER REQUEST: {message}")
    return coerce_decision(run.content)