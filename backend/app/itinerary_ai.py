"""Full-day itinerary planned by an Agno agent.

The agent only picks OPTION NUMBERS from real nearby places. Everything it says is validated,
empty or invalid slots are filled with the nearest real place, and OSRM does the timing.
If the agent fails, the rule-based plan (itinerary.build_trip) is used.
"""
import re
from functools import lru_cache
from typing import Optional

from pydantic import BaseModel, Field

from .config import settings
from .geo import haversine_km
from .itinerary import (MAX_ATTRACTION_KM, MAX_FOOD_KM, SLOTS, build_trip,
                        fill_recommendations, fill_slots, make_stop, recalculate)
from .llm import extract_json
from .models import Place, TripState


class Pick(BaseModel):
    option: int
    reason: str = ""


class PlanChoice(BaseModel):
    day_start: str = "08:30"
    main_duration_min: int = 90
    morning_attraction: Optional[int] = None
    lunch_restaurant: Optional[int] = None
    afternoon_attraction: Optional[int] = None
    tea_cafe: Optional[int] = None
    sunset_spot: Optional[int] = None
    dinner_restaurant: Optional[int] = None
    recommended: list[Pick] = Field(default_factory=list)
    summary: str = ""


SYSTEM = (
    "You plan a relaxed FULL-DAY trip in Kerala, India around one main place. "
    "The day is: main place first, then a late-morning attraction, lunch, an afternoon attraction, "
    "tea at a cafe, an evening spot, and dinner. "
    "Fill every slot with a numbered option of the right type whenever a suitable one exists. "
    "Never use the same option twice. Prefer options close to each other and to the main place. "
    "Also recommend up to 5 OTHER attractions from the list that are worth visiting but are not used in the day. "
    "If the weather has rain or a storm, keep outdoor time short and mention safety in the summary. "
    "Only use option numbers that appear in the list."
)

JSON_RULES = (
    ' Reply with ONLY one JSON object and nothing else, with these keys: '
    '"day_start" (HH:MM between 07:30 and 09:30), "main_duration_min" (number 60 to 150), '
    '"morning_attraction", "lunch_restaurant", "afternoon_attraction", "tea_cafe", "sunset_spot", '
    '"dinner_restaurant" (each one an option number, or null), '
    '"recommended" (a list of up to 5 objects like {"option": 3, "reason": "short reason"}), '
    '"summary" (three friendly sentences describing the whole day, with one weather or safety tip).'
)


@lru_cache(maxsize=1)
def _agent():
    from agno.agent import Agent
    from agno.models.google import Gemini

    model = Gemini(id=settings.gemini_model, api_key=settings.gemini_api_key)
    return Agent(model=model, instructions=SYSTEM + JSON_RULES)


def _options(nearby: list[Place]) -> list[Place]:
    attractions = [p for p in nearby if p.kind == "attraction"][:14]
    restaurants = [p for p in nearby if p.kind == "restaurant"][:10]
    cafes = [p for p in nearby if p.kind == "cafe"][:8]
    return attractions + restaurants + cafes


async def build_trip_ai(session_id: str, name: str, district: str, kind: str,
                        lat: float, lon: float, nearby: list[Place],
                        weather: str = "") -> TripState:
    kind = kind if kind in ("waterfall", "viewpoint") else "viewpoint"
    opts = _options(nearby)

    try:
        text = "\n".join(
            f"[{i}] {p.kind}: {p.name}, {haversine_km(lat, lon, p.lat, p.lon):.1f} km from the main place"
            for i, p in enumerate(opts)
        ) or "(no nearby places were found)"
        run = await _agent().arun(
            f"MAIN PLACE: {name} ({kind}) in {district or 'Kerala'}\n"
            f"CURRENT WEATHER: {weather or 'unknown'}\n\nOPTIONS:\n{text}")
        plan = PlanChoice.model_validate(extract_json(str(run.content)))
    except Exception as e:
        print(f"[itinerary_ai] falling back to the rule-based plan: {type(e).__name__}: {e}")
        return await build_trip(session_id, name, district, kind, lat, lon, nearby)

    trip = TripState(session_id=session_id, destination=name, district=district,
                     day_start="08:30", candidates=nearby)
    if re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", plan.day_start or "") \
            and "07:30" <= plan.day_start <= "09:30":
        trip.day_start = plan.day_start

    main = make_stop(1, name, kind, lat, lon)
    main.duration_min = min(max(plan.main_duration_min or 0, 60), 150)
    trip.stops.append(main)

    # validate the agent's picks; anything invalid is left empty and filled by fill_slots
    choices: dict[str, Place] = {}
    taken = {name.lower()}
    for field, category, _ in SLOTS:
        idx = getattr(plan, field, None)
        if not isinstance(idx, int) or not 0 <= idx < len(opts):
            continue
        p = opts[idx]
        limit = MAX_ATTRACTION_KM if category == "attraction" else MAX_FOOD_KM
        if p.kind == category and p.name.lower() not in taken \
                and haversine_km(lat, lon, p.lat, p.lon) <= limit:
            choices[field] = p
            taken.add(p.name.lower())
    fill_slots(trip, choices)

    picks = [(opts[pk.option], pk.reason.strip()) for pk in plan.recommended[:8]
             if 0 <= pk.option < len(opts) and opts[pk.option].kind == "attraction"]
    fill_recommendations(trip, picks)

    trip.summary = (plan.summary or "")[:500]
    return await recalculate(trip)