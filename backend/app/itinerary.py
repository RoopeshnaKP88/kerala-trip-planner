"""Full-day itinerary: slot template, recommendations, rule-based builder and OSRM re-timing."""
import math

from .geo import haversine_km, route
from .models import Place, Recommendation, Stop, TripState

DURATIONS = {"waterfall": 90, "viewpoint": 60, "attraction": 60, "restaurant": 60, "cafe": 45}
OUTDOOR = {"waterfall": True, "viewpoint": True, "attraction": True, "restaurant": False, "cafe": False}

# The shape of a full day after the main place: (slot name, category, earliest start time).
SLOTS = [
    ("morning_attraction", "attraction", None),
    ("lunch_restaurant", "restaurant", "12:30"),
    ("afternoon_attraction", "attraction", "14:30"),
    ("tea_cafe", "cafe", "16:00"),
    ("sunset_spot", "attraction", "17:15"),
    ("dinner_restaurant", "restaurant", "19:00"),
]
MAX_ATTRACTION_KM = 40.0  # farthest an extra attraction may be from the previous stop
MAX_FOOD_KM = 25.0
MAX_RECOMMENDATIONS = 5
MAX_RECOMMEND_KM = 60.0


def hm_to_min(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def min_to_hm(m: int) -> str:
    return f"{(m // 60) % 24:02d}:{m % 60:02d}"


def make_stop(stop_id: int, name: str, kind: str, lat: float, lon: float,
              earliest: str | None = None) -> Stop:
    return Stop(
        id=stop_id, name=name, kind=kind, lat=lat, lon=lon,
        outdoor=OUTDOOR[kind], duration_min=DURATIONS[kind], earliest=earliest,
    )


def pick_candidate(trip: TripState, category: str, ref_lat: float, ref_lon: float,
                   max_km: float | None = None) -> Place | None:
    used = {s.name.lower() for s in trip.stops}
    pool = [p for p in trip.candidates if p.kind == category and p.name.lower() not in used]
    if max_km is not None:
        pool = [p for p in pool if haversine_km(ref_lat, ref_lon, p.lat, p.lon) <= max_km]
    pool.sort(key=lambda p: haversine_km(ref_lat, ref_lon, p.lat, p.lon))
    return pool[0] if pool else None


def next_id(trip: TripState) -> int:
    return max((s.id for s in trip.stops), default=0) + 1


def fill_slots(trip: TripState, choices: dict | None = None) -> None:
    """Add the rest of the day. 'choices' maps a slot name to a Place picked by the AI.
    Any slot without a valid choice gets the nearest real place instead."""
    choices = choices or {}
    for field, category, earliest in SLOTS:
        last = trip.stops[-1]
        used = {s.name.lower() for s in trip.stops}
        place = choices.get(field)
        if place is not None and place.name.lower() in used:
            place = None
        if place is None:
            limit = MAX_ATTRACTION_KM if category == "attraction" else MAX_FOOD_KM
            place = pick_candidate(trip, category, last.lat, last.lon, max_km=limit)
        if place is not None:
            trip.stops.append(make_stop(next_id(trip), place.name, category,
                                        place.lat, place.lon, earliest))


def fill_recommendations(trip: TripState, picks: list | None = None) -> None:
    """Extra places to visit (not scheduled). 'picks' is a list of (Place, reason) chosen by the AI;
    the list is topped up with the nearest unused attractions."""
    main = trip.stops[0]
    used = {s.name.lower() for s in trip.stops}
    recs: list[Recommendation] = []

    def add(place: Place, reason: str) -> None:
        if place.name.lower() in used or len(recs) >= MAX_RECOMMENDATIONS:
            return
        dist = haversine_km(main.lat, main.lon, place.lat, place.lon)
        if dist > MAX_RECOMMEND_KM:
            return
        used.add(place.name.lower())
        recs.append(Recommendation(
            name=place.name, lat=place.lat, lon=place.lon, kind="attraction",
            distance_km=round(dist, 1),
            reason=(reason or f"About {dist:.0f} km from {main.name}")[:160]))

    for place, reason in picks or []:
        add(place, reason)
    pool = sorted((p for p in trip.candidates if p.kind == "attraction"),
                  key=lambda p: haversine_km(main.lat, main.lon, p.lat, p.lon))
    for p in pool:
        add(p, "")
    trip.recommendations = recs


async def recalculate(trip: TripState) -> TripState:
    """Recompute travel legs and start times. Overlaps are impossible by construction."""
    t = hm_to_min(trip.day_start)
    prev: Stop | None = None
    for s in trip.stops:
        if prev:
            leg = await route(prev.lat, prev.lon, s.lat, s.lon)
            s.leg_from_prev = leg
            t += math.ceil(leg.duration_min)
        else:
            s.leg_from_prev = None
        earliest = s.earliest or ("12:30" if s.kind == "restaurant" else None)
        if earliest:
            t = max(t, hm_to_min(earliest))
        s.start = min_to_hm(t)
        t += s.duration_min
        prev = s
    trip.warnings = ["The plan runs past 9:30 PM; consider removing a stop."] if t > 21 * 60 + 30 else []
    return trip


async def build_trip(session_id: str, name: str, district: str, kind: str,
                     lat: float, lon: float, nearby: list[Place]) -> TripState:
    """Rule-based full day (no AI). Used when USE_AI_ITINERARY=false or the AI fails."""
    kind = kind if kind in ("waterfall", "viewpoint") else "viewpoint"
    trip = TripState(session_id=session_id, destination=name, district=district,
                     day_start="08:30", candidates=nearby)
    trip.stops.append(make_stop(1, name, kind, lat, lon))
    fill_slots(trip)
    fill_recommendations(trip)
    return await recalculate(trip)