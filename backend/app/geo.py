"""Geocoding, weather, nearby places (food AND attractions) and routing (all free APIs)."""
import asyncio
import math
import re
import time

import httpx

from .models import Leg, Place

HEADERS = {"User-Agent": "kerala-trip-planner/1.0 (student project)"}
NOMINATIM = "https://nominatim.openstreetmap.org/search"

WMO = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Fog", 51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain", 80: "Rain showers",
    81: "Rain showers", 82: "Violent showers", 95: "Thunderstorm",
    96: "Thunderstorm with hail", 99: "Thunderstorm with hail",
}

# All Overpass servers are asked AT THE SAME TIME and the first good answer wins.
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
OVERPASS_TIMEOUT = httpx.Timeout(12.0, connect=5.0)

_nearby_cache: dict[tuple[float, float], list[Place]] = {}
_inflight: dict[tuple[float, float], asyncio.Task] = {}
_nom_lock = asyncio.Lock()
_nom_last = 0.0


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def in_kerala(lat: float, lon: float) -> bool:
    return 8.0 <= lat <= 12.9 and 74.8 <= lon <= 77.5


async def _nominatim(client: httpx.AsyncClient, params: dict) -> httpx.Response:
    """All Nominatim calls go through here, so they stay under 1 request per second."""
    global _nom_last
    async with _nom_lock:
        wait = 1.1 - (time.monotonic() - _nom_last)
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            return await client.get(NOMINATIM, params=params)
        finally:
            _nom_last = time.monotonic()


def _join(*parts: str) -> str:
    return ", ".join(p for p in parts if p)


def _name_variants(name: str, district: str) -> list[str]:
    base = name.strip()
    short = re.sub(r"\b(water ?falls?|falls?|view ?point|peak)\b", "", base, flags=re.I)
    short = short.strip(" ,-")
    variants = [
        _join(base, district, "Kerala", "India"),
        _join(base, "Kerala", "India"),
    ]
    if short and short.lower() != base.lower():
        variants += [
            _join(short, "waterfall", "Kerala", "India"),
            _join(short, district, "Kerala", "India"),
        ]
    seen, unique = set(), []
    for v in variants:  # remove duplicates, keep order
        if v.lower() not in seen:
            seen.add(v.lower())
            unique.append(v)
    return unique[:4]


async def geocode(name: str, district: str = "") -> tuple[float, float] | None:
    async with httpx.AsyncClient(timeout=15, headers=HEADERS) as c:
        for q in _name_variants(name, district):
            try:
                r = await _nominatim(c, {"q": q, "format": "json", "limit": 1, "countrycodes": "in"})
            except httpx.HTTPError:
                continue
            if r.status_code == 200 and r.json():
                hit = r.json()[0]
                lat, lon = float(hit["lat"]), float(hit["lon"])
                if in_kerala(lat, lon):
                    return lat, lon
    return None


async def weather(lat: float, lon: float) -> dict:
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,precipitation,weather_code,wind_speed_10m",
                "timezone": "Asia/Kolkata",
            },
        )
        r.raise_for_status()
        cur = r.json()["current"]
    return {
        "temperature_c": cur["temperature_2m"],
        "precipitation_mm": cur["precipitation"],
        "wind_kmh": cur["wind_speed_10m"],
        "summary": WMO.get(cur["weather_code"], "Unknown"),
    }


# ---------------- Overpass (main source) ----------------
async def _one_overpass(url: str, query: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=OVERPASS_TIMEOUT, headers=HEADERS) as c:
        r = await c.post(url, data={"data": query})
        if r.status_code != 200:
            raise RuntimeError(f"answered {r.status_code}")
        return r.json().get("elements", [])


async def _run_overpass(query: str, label: str) -> list[dict] | None:
    """Asks every server at the same time. Returns the first good answer (maybe an empty list),
    or None if EVERY server failed."""
    tasks = [asyncio.create_task(_one_overpass(u, query)) for u in OVERPASS_URLS]
    try:
        for fut in asyncio.as_completed(tasks):
            try:
                return await fut
            except Exception as e:
                print(f"[overpass] one server failed: {type(e).__name__} ({label})")
        return None
    finally:
        for t in tasks:
            t.cancel()


def _food_query(lat: float, lon: float, radius: int) -> str:
    return f"""
    [out:json][timeout:15];
    (
      nwr["amenity"~"^(cafe|restaurant)$"]["name"](around:{radius},{lat},{lon});
      nwr["tourism"~"^(hotel|guest_house|resort|homestay)$"]["name"](around:{radius},{lat},{lon});
    );
    out center 60;
    """


def _attraction_query(lat: float, lon: float, radius: int) -> str:
    a = f"(around:{radius},{lat},{lon})"
    return f"""
    [out:json][timeout:15];
    (
      nwr["tourism"~"^(attraction|viewpoint|picnic_site|museum|zoo|theme_park)$"]["name"]{a};
      nwr["natural"~"^(waterfall|peak|beach|spring)$"]["name"]{a};
      nwr["waterway"="waterfall"]["name"]{a};
      nwr["leisure"~"^(park|garden|nature_reserve)$"]["name"]{a};
      nwr["historic"~"^(monument|ruins|fort|castle|memorial)$"]["name"]{a};
    );
    out center 120;
    """


def _to_places(elements: list[dict], lat: float, lon: float,
               attractions: bool = False, limit: int = 30) -> list[Place]:
    places: list[Place] = []
    seen: set[str] = set()
    for e in elements:
        tags = e.get("tags", {})
        name = tags.get("name")
        if not name or name.lower() in seen:
            continue
        plat = e.get("lat") or e.get("center", {}).get("lat")
        plon = e.get("lon") or e.get("center", {}).get("lon")
        if plat is None or plon is None:
            continue
        if attractions:
            if haversine_km(lat, lon, plat, plon) < 0.3:  # that is the main place itself
                continue
            kind = "attraction"
        else:
            amenity = tags.get("amenity")
            kind = amenity if amenity in ("cafe", "restaurant") else "stay"
        seen.add(name.lower())
        places.append(Place(name=name, lat=plat, lon=plon, kind=kind))
    places.sort(key=lambda p: haversine_km(lat, lon, p.lat, p.lon))
    return places[:limit]


# ---------------- Nominatim (backup source) ----------------
async def _nominatim_search(lat: float, lon: float, terms: list[str], kind: str,
                            half_box: float, skip_near_main: bool) -> list[Place]:
    box = f"{lon - half_box},{lat + half_box},{lon + half_box},{lat - half_box}"  # left, top, right, bottom
    places: list[Place] = []
    seen: set[str] = set()
    async with httpx.AsyncClient(timeout=15, headers=HEADERS) as c:
        for term in terms:
            try:
                r = await _nominatim(c, {"q": term, "format": "json", "limit": 15,
                                         "viewbox": box, "bounded": 1, "countrycodes": "in"})
                if r.status_code != 200:
                    continue
                for h in r.json():
                    name = h.get("name") or h.get("display_name", "").split(",")[0]
                    plat, plon = float(h["lat"]), float(h["lon"])
                    if not name or name.lower() in seen:
                        continue
                    if skip_near_main and haversine_km(lat, lon, plat, plon) < 0.3:
                        continue
                    seen.add(name.lower())
                    places.append(Place(name=name, lat=plat, lon=plon, kind=kind if kind != "term" else term))
            except (httpx.HTTPError, ValueError, KeyError):
                continue
    places.sort(key=lambda p: haversine_km(lat, lon, p.lat, p.lon))
    return places


# ---------------- Public: nearby() ----------------
async def _nearby_food(lat: float, lon: float, radius: int) -> list[Place]:
    elements: list[dict] = []
    for r_m in (radius, 12000, 25000):  # remote place? widen the search step by step
        got = await _run_overpass(_food_query(lat, lon, r_m), f"food {r_m} m")
        if got is None:  # every server failed: widening would only be slower
            break
        elements = got
        if len(elements) >= 3:
            break
    places = _to_places(elements, lat, lon, limit=30)
    if not places:
        places = await _nominatim_search(lat, lon, ["restaurant", "cafe"], "term", 0.2, False)
        places = places[:30]
    print(f"[nearby] {len(places)} cafes/restaurants/stays near {lat}, {lon}")
    return places


async def _nearby_attractions(lat: float, lon: float) -> list[Place]:
    places: list[Place] = []
    for r_m in (20000, 35000):
        got = await _run_overpass(_attraction_query(lat, lon, r_m), f"attractions {r_m} m")
        if got is None:
            break
        places = _to_places(got, lat, lon, attractions=True, limit=20)
        if len(places) >= 4:
            break
    if len(places) < 3:  # Overpass gave too little: add a few from Nominatim
        extra = await _nominatim_search(lat, lon, ["waterfall", "viewpoint", "park", "temple", "dam"],
                                        "attraction", 0.3, True)
        names = {p.name.lower() for p in places}
        places += [Place(name=p.name, lat=p.lat, lon=p.lon, kind="attraction")
                   for p in extra if p.name.lower() not in names]
        places.sort(key=lambda p: haversine_km(lat, lon, p.lat, p.lon))
    print(f"[nearby] {len(places)} attractions near {lat}, {lon}")
    return places[:20]


def _key(lat: float, lon: float) -> tuple[float, float]:
    return (round(lat, 2), round(lon, 2))


async def _fill_cache(key: tuple[float, float], lat: float, lon: float, radius: int) -> list[Place]:
    try:
        food, attractions = await asyncio.gather(
            _nearby_food(lat, lon, radius), _nearby_attractions(lat, lon))
    except Exception as e:
        print(f"[nearby] failed: {type(e).__name__}: {e}")
        return []
    places = food + attractions
    if places:
        _nearby_cache[key] = places
    return places


def _start(key: tuple[float, float], lat: float, lon: float, radius: int) -> asyncio.Task:
    """One search per location: a second request for the same place waits for the first."""
    task = _inflight.get(key)
    if task is None:
        task = asyncio.create_task(_fill_cache(key, lat, lon, radius))
        _inflight[key] = task
        task.add_done_callback(lambda _t, k=key: _inflight.pop(k, None))
    return task


def prefetch_nearby(lat: float, lon: float, radius: int = 5000) -> None:
    """Start searching in the background and return at once. The plan step picks up the result."""
    key = _key(lat, lon)
    if key not in _nearby_cache:
        _start(key, lat, lon, radius)


async def nearby(lat: float, lon: float, radius: int = 5000) -> list[Place]:
    """Cafes, restaurants, stays AND attractions around a point (cached per location)."""
    key = _key(lat, lon)
    if key in _nearby_cache:
        return _nearby_cache[key]
    return await asyncio.shield(_start(key, lat, lon, radius))


async def route(a_lat, a_lon, b_lat, b_lon) -> Leg:
    """OSRM driving route; falls back to a straight-line estimate if OSRM is down."""
    url = f"https://router.project-osrm.org/route/v1/driving/{a_lon},{a_lat};{b_lon},{b_lat}"
    try:
        async with httpx.AsyncClient(timeout=15, headers=HEADERS) as c:
            r = await c.get(url, params={"overview": "false"})
            r.raise_for_status()
            rt = r.json()["routes"][0]
            return Leg(distance_km=round(rt["distance"] / 1000, 1), duration_min=round(rt["duration"] / 60, 1))
    except (httpx.HTTPError, KeyError, IndexError):
        km = haversine_km(a_lat, a_lon, b_lat, b_lon) * 1.4
        return Leg(distance_km=round(km, 1), duration_min=round(km / 30 * 60, 1))