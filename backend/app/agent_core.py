"""Shared by all three chat frameworks.

Each framework file only answers ONE question:  decide(trip, message) -> ChatDecision.
Validation, editing the plan and OSRM re-timing live here, so the safety logic is identical.
"""
import json
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .itinerary import make_stop, next_id, pick_candidate, recalculate
from .llm import extract_json
from .models import (AddStop, ChangeDuration, Envelope, NoChange, RemoveStop,
                     ReplaceStop, TripState)


class ChatDecision(BaseModel):
    """What the LLM must fill in. Flat on purpose: it is the most reliable across models."""
    action: Literal["replace_stop", "remove_stop", "add_stop", "change_duration", "no_change"] = Field(
        description="The single change to make to the plan.")
    stop_id: Optional[int] = Field(None, description="Id of the stop to replace, remove or change.")
    new_category: Optional[Literal["cafe", "restaurant"]] = Field(
        None, description="For replace_stop: the kind of indoor place to swap in.")
    category: Optional[Literal["cafe", "restaurant"]] = Field(
        None, description="For add_stop: the kind of place to add.")
    after_stop_id: Optional[int] = Field(None, description="For add_stop: insert after this stop id.")
    duration_min: Optional[int] = Field(None, description="For change_duration: minutes, 15 to 240.")
    reply: str = Field(description="One short, friendly sentence telling the user what you did.")


INSTRUCTIONS = (
    "You are a trip-replanning assistant for a one-day Kerala itinerary. "
    "You receive the current plan as JSON and the user's request. "
    "Choose exactly ONE action: replace_stop, remove_stop, add_stop, change_duration or no_change. "
    "Use only stop ids that exist in the plan. Never rewrite the whole plan. "
    "Outdoor stops (waterfall, viewpoint) are a bad idea in rain, so swap them for a cafe or restaurant. "
    "If the request is unclear or impossible, choose no_change and explain in the reply."
)


def plan_json(trip: TripState) -> str:
    return json.dumps([
        s.model_dump(include={"id", "name", "kind", "start", "duration_min", "outdoor"})
        for s in trip.stops
    ])


def coerce_decision(obj) -> ChatDecision:
    """Frameworks return a model, a dict or a string. Turn any of them into a ChatDecision."""
    if isinstance(obj, ChatDecision):
        return obj
    if isinstance(obj, BaseModel):
        return ChatDecision.model_validate(obj.model_dump())
    if isinstance(obj, dict):
        return ChatDecision.model_validate(obj)
    if isinstance(obj, str):
        return ChatDecision.model_validate(extract_json(obj))
    raise ValueError(f"Unsupported decision type: {type(obj)}")


def _find(trip: TripState, stop_id: int):
    return next((s for s in trip.stops if s.id == stop_id), None)


async def apply_decision(trip: TripState, decision: ChatDecision) -> tuple[TripState, str]:
    try:
        data = decision.model_dump(exclude_none=True)
        reply = data.pop("reply", "") or "Done."
        env = Envelope.model_validate({"action": data, "reply": reply})  # strict check
    except Exception:
        return trip, "Sorry, I couldn't turn that into a safe change. Could you rephrase?"

    a = env.action

    if isinstance(a, NoChange):
        return trip, env.reply

    if isinstance(a, ReplaceStop):
        old = _find(trip, a.stop_id)
        if not old:
            return trip, f"There is no stop number {a.stop_id}."
        p = pick_candidate(trip, a.new_category, old.lat, old.lon)
        if not p:
            return trip, f"I couldn't find a nearby {a.new_category} to swap in."
        trip.stops[trip.stops.index(old)] = make_stop(
            next_id(trip), p.name, a.new_category, p.lat, p.lon)

    elif isinstance(a, RemoveStop):
        old = _find(trip, a.stop_id)
        if not old:
            return trip, f"There is no stop number {a.stop_id}."
        if len(trip.stops) == 1:
            return trip, "I can't remove the only stop."
        trip.stops.remove(old)

    elif isinstance(a, AddStop):
        after = _find(trip, a.after_stop_id)
        if not after:
            return trip, f"There is no stop number {a.after_stop_id}."
        p = pick_candidate(trip, a.category, after.lat, after.lon)
        if not p:
            return trip, f"I couldn't find a nearby {a.category} to add."
        trip.stops.insert(trip.stops.index(after) + 1,
                          make_stop(next_id(trip), p.name, a.category, p.lat, p.lon))

    elif isinstance(a, ChangeDuration):
        s = _find(trip, a.stop_id)
        if not s:
            return trip, f"There is no stop number {a.stop_id}."
        s.duration_min = a.duration_min

    return await recalculate(trip), env.reply