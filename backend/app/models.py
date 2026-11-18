"""Strict data models (TripState) and the actions the LLM may emit."""
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field

Category = Literal["cafe", "restaurant"]


class Place(BaseModel):
    name: str
    lat: float
    lon: float
    kind: str  # cafe | restaurant | stay | attraction


class Leg(BaseModel):
    distance_km: float
    duration_min: float


class Stop(BaseModel):
    id: int
    name: str
    kind: Literal["waterfall", "viewpoint", "attraction", "cafe", "restaurant"]
    lat: float
    lon: float
    outdoor: bool
    start: str = "09:00"  # HH:MM
    duration_min: int = 60
    earliest: Optional[str] = None  # the stop never starts before this time (HH:MM)
    leg_from_prev: Optional[Leg] = None


class Recommendation(BaseModel):
    """An extra place worth visiting. It is shown with the plan and on the map, but not scheduled."""
    name: str
    lat: float
    lon: float
    kind: str = "attraction"
    distance_km: float = 0.0
    reason: str = ""


class TripState(BaseModel):
    session_id: str
    destination: str
    district: str = ""
    day_start: str = "08:30"
    stops: list[Stop] = []
    recommendations: list[Recommendation] = []
    candidates: list[Place] = []  # nearby places the planner and the agent may use
    warnings: list[str] = []
    summary: str = ""  # short AI-written overview of the day


# ---- actions the LLM is allowed to produce (anything else is rejected) ----
class ReplaceStop(BaseModel):
    action: Literal["replace_stop"]
    stop_id: int
    new_category: Category


class RemoveStop(BaseModel):
    action: Literal["remove_stop"]
    stop_id: int


class AddStop(BaseModel):
    action: Literal["add_stop"]
    category: Category
    after_stop_id: int


class ChangeDuration(BaseModel):
    action: Literal["change_duration"]
    stop_id: int
    duration_min: int = Field(ge=15, le=240)


class NoChange(BaseModel):
    action: Literal["no_change"]


Action = Annotated[
    Union[ReplaceStop, RemoveStop, AddStop, ChangeDuration, NoChange],
    Field(discriminator="action"),
]


class Envelope(BaseModel):
    action: Action
    reply: str = ""