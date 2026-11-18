"""Trip assistant chatbot: an Agno Team that routes each message to a specialist agent.

Agents: Budget (uses a Python calculator), Friend, Guide, General helper.
"""
import math

from agno.agent import Agent
from agno.models.google import Gemini
from agno.team import Team

from .config import settings
from .models import TripState

MAX_TURNS = 6
_history: dict[str, list[tuple[str, str]]] = {}


def _model():
    return Gemini(id=settings.gemini_model, api_key=settings.gemini_api_key)


def _search_tools() -> list:
    """Web search for the General agent. Skipped quietly if 'ddgs' is not installed."""
    try:
        from agno.tools.duckduckgo import DuckDuckGoTools
        return [DuckDuckGoTools()]
    except Exception:
        return []


def trip_context(trip: TripState | None, place: str, district: str) -> str:
    if trip:
        lines = [f"Place: {trip.destination} ({trip.district})"]
        for s in trip.stops:
            leg = f", {s.leg_from_prev.distance_km} km drive from the previous stop" if s.leg_from_prev else ""
            lines.append(f"- {s.start} {s.name} [{s.kind}], {s.duration_min} min{leg}")
        if trip.recommendations:
            lines.append("Recommended extra places: " + "; ".join(
                f"{r.name} ({r.distance_km} km away)" for r in trip.recommendations))
        if trip.summary:
            lines.append(f"Summary: {trip.summary}")
        return "\n".join(lines)
    if place:
        return f"Place: {place} ({district or 'Kerala'}). No itinerary has been made yet."
    return "No place has been chosen yet."


def make_budget_tool(trip: TripState | None):
    """Builds the calculator tool, bound to the current plan."""
    stops = trip.stops if trip else []
    plan_km = sum(s.leg_from_prev.distance_km for s in stops if s.leg_from_prev)
    n_lunch = sum(1 for s in stops if s.kind == "restaurant") if trip else 1
    n_cafe = sum(1 for s in stops if s.kind == "cafe") if trip else 1

    def calculate_trip_budget(
        people: int = 2,
        distance_from_home_km: float = 0.0,
        cost_per_km: float = 12.0,
        lunch_per_person: float = 300.0,
        cafe_per_person: float = 150.0,
        entry_fee_per_person: float = 50.0,
        parking_and_misc: float = 100.0,
        nights: int = 0,
        stay_per_room_per_night: float = 0.0,
    ) -> str:
        """Calculate the trip budget in Indian rupees. ALWAYS use this tool for any cost figure.

        Args:
            people: Number of travellers.
            distance_from_home_km: One-way distance from where the group starts to the first stop (0 if unknown).
            cost_per_km: Cab or fuel cost per km for the whole vehicle.
            lunch_per_person: Average lunch cost for one person.
            cafe_per_person: Average cafe snack cost for one person.
            entry_fee_per_person: Entry or ticket fee at the main place for one person.
            parking_and_misc: Parking and small expenses for the whole group.
            nights: Number of nights of stay (0 for a day trip).
            stay_per_room_per_night: Cost of one room for one night.
        """
        people = max(1, int(people))
        nights = max(0, int(nights))
        total_km = plan_km + 2 * max(0.0, distance_from_home_km)
        transport = total_km * max(0.0, cost_per_km)
        lunch = n_lunch * people * max(0.0, lunch_per_person)
        cafe = n_cafe * people * max(0.0, cafe_per_person)
        entry = people * max(0.0, entry_fee_per_person)
        misc = max(0.0, parking_and_misc)
        rooms = math.ceil(people / 2) if nights else 0
        stay = rooms * nights * max(0.0, stay_per_room_per_night)
        total = transport + lunch + cafe + entry + misc + stay
        return (
            f"Budget estimate for {people} people (INR):\n"
            f"- Transport: {total_km:.0f} km x Rs {cost_per_km:.0f}/km = Rs {transport:,.0f}\n"
            f"- Lunch: {n_lunch} meal(s) x {people} x Rs {lunch_per_person:.0f} = Rs {lunch:,.0f}\n"
            f"- Cafe: {n_cafe} stop(s) x {people} x Rs {cafe_per_person:.0f} = Rs {cafe:,.0f}\n"
            f"- Entry fees: {people} x Rs {entry_fee_per_person:.0f} = Rs {entry:,.0f}\n"
            f"- Parking and misc: Rs {misc:,.0f}\n"
            f"- Stay: {rooms} room(s) x {nights} night(s) x Rs {stay_per_room_per_night:.0f} = Rs {stay:,.0f}\n"
            f"TOTAL: Rs {total:,.0f}   |   PER PERSON: Rs {total / people:,.0f}\n"
            "All rates are assumptions, not confirmed prices."
        )

    return calculate_trip_budget


def build_team(trip: TripState | None) -> Team:
    budget = Agent(
        name="Budget Agent",
        role="Calculates trip costs and splits them between travellers.",
        model=_model(),
        tools=[make_budget_tool(trip)],
        instructions=[
            "Use the calculate_trip_budget tool for EVERY number. Never do the arithmetic yourself.",
            "If the user did not say how many people, assume 2 and say so.",
            "If the user gives real prices (cab fare, entry fee, room rate), pass them to the tool.",
            "Report the tool's breakdown clearly, then say these are estimates and offer to recalculate "
            "with real prices, a different group size or an overnight stay.",
            "Write amounts in Indian rupees.",
        ],
        markdown=True,
    )
    friend = Agent(
        name="Friend Agent",
        role="A warm, casual travel buddy who chats, encourages and gives friendly tips.",
        model=_model(),
        instructions=[
            "Talk like a friendly travel buddy: warm, relaxed, short replies, a little humour, "
            "at most one emoji.",
            "You are an AI. Never claim you have visited places or have personal experiences.",
            "If the user sounds worried (rain, slippery rocks, travelling alone), reassure them and "
            "give one practical safety tip.",
            "Use the trip context when it helps.",
        ],
        markdown=True,
    )
    guide = Agent(
        name="Guide Agent",
        role="A local-style guide who explains the place the user uploaded.",
        model=_model(),
        instructions=[
            "Explain the place from the trip context: what it is, what to see, best season, "
            "how to reach it, safety, and what is nearby.",
            "Only state what you are reasonably sure about. Say 'not confirmed' for details you "
            "are unsure of, especially entry fees, timings and closures, and tell the user to "
            "check locally before travelling.",
            "Keep it under 200 words unless the user asks for more.",
        ],
        markdown=True,
    )
    general = Agent(
        name="General Agent",
        role="Answers any other question clearly and correctly.",
        model=_model(),
        tools=_search_tools(),
        instructions=[
            "Answer the question directly and correctly, in a few clear sentences.",
            "Use web search for current or time-sensitive facts if the tool is available.",
            "If you do not know, say so honestly instead of guessing.",
            "If the user wants to change the itinerary (add, remove or replace a stop, change durations), "
            "tell them to switch the chat mode to 'Edit my plan'.",
        ],
        markdown=True,
    )
    return Team(
        name="Kerala Trip Assistant",
        model=_model(),
        members=[budget, friend, guide, general],
        respond_directly=True,
        instructions=[
            "Send each message to exactly ONE member.",
            "Budget Agent: costs, money, price, how much, split between people.",
            "Guide Agent: questions about the place itself, its history, best time, how to reach it, "
            "safety, what to see.",
            "Friend Agent: chit-chat, feelings, nervousness, excitement, encouragement, casual advice.",
            "General Agent: everything else, and requests to change the itinerary.",
        ],
        markdown=True,
    )


def _member_name(run) -> str:
    """Best effort: which agent answered. Falls back to 'assistant'."""
    try:
        responses = getattr(run, "member_responses", None) or []
        if responses:
            return getattr(responses[0], "agent_name", None) or "assistant"
    except Exception:
        pass
    return "assistant"


async def ask_assistant(key: str, message: str, trip: TripState | None,
                        place: str, district: str) -> tuple[str, str]:
    history = _history.get(key, [])[-MAX_TURNS * 2:]
    history_text = "\n".join(f"{who}: {text}" for who, text in history) or "(none)"
    prompt = (
        f"TRIP CONTEXT:\n{trip_context(trip, place, district)}\n\n"
        f"RECENT CHAT:\n{history_text}\n\n"
        f"USER MESSAGE: {message}"
    )
    run = await build_team(trip).arun(prompt)
    reply = str(run.content).strip() or "Sorry, I could not come up with an answer. Please try again."

    if len(_history) > 200:
        _history.clear()
    _history.setdefault(key, []).extend([("User", message), ("Assistant", reply)])
    return reply, _member_name(run)