"""Plan-editing chatbot. It uses Agno only: Agno proposes ONE change, agent_core validates and applies it."""
from .agent_core import apply_decision
from .models import TripState


async def replan(trip: TripState, message: str) -> tuple[TripState, str]:
    try:
        from .agent_agno import decide
        decision = await decide(trip, message)
    except ImportError as e:
        return trip, f"Agno is not installed in this environment ({e}). Run: pip install -U agno google-genai"
    except Exception as e:  # model busy, bad output, timeout: the plan stays untouched
        print(f"[agent] error: {type(e).__name__}: {e}")
        return trip, "Sorry, I couldn't turn that into a safe change. Could you rephrase?"
    return await apply_decision(trip, decision)
