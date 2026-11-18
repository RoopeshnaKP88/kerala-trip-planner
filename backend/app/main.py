import asyncio
import difflib
import importlib.util
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import agent, db, geo, store, vlm
from .config import settings
from .itinerary import build_trip
from .itinerary_ai import build_trip_ai
from .llm import ask_json
from .models import Place, TripState
from .places import DISTRICT_CENTERS, KNOWN_PLACES

UPLOADS = Path(settings.upload_dir)
UPLOADS.mkdir(exist_ok=True)
MAX_BYTES = 10 * 1024 * 1024


async def _cleanup_loop():
    """Privacy: delete uploaded photos older than 24 hours (checked hourly)."""
    while True:
        cutoff = time.time() - 24 * 3600
        for f in UPLOADS.glob("*.jpg"):
            if f.stat().st_mtime < cutoff:
                f.unlink(missing_ok=True)
        await asyncio.sleep(3600)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        db.init_db()
    except Exception as e:  # app still works without Postgres
        print(f"[db] could not initialise database: {e}")
    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()


app = FastAPI(title="Kerala Smart Trip Planner", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "python": sys.executable,
        "chat_framework": "agno",
        "model": settings.gemini_model,
        "agno_installed": importlib.util.find_spec("agno") is not None,
        "ai_itinerary": settings.use_ai_itinerary,
    }

# ---------------- Photo recognition + map data ----------------
def _district_center(district: str):
    if not district:
        return None
    key = difflib.get_close_matches(district.strip().lower(), list(DISTRICT_CENTERS), n=1, cutoff=0.7)
    return DISTRICT_CENTERS[key[0]] if key else None


async def _ai_text_estimate(name: str, district: str):
    """Ask the AI (text only) for rough coordinates of a place. Returns (lat, lon) or None."""
    try:
        data = await ask_json(
            f'Give the approximate GPS coordinates of "{name}" in {district or "Kerala"}, Kerala, India. '
            'Return JSON only, like {"latitude": 10.1, "longitude": 76.2}. '
            "If you do not know this place, return null for both values. Do not guess."
        )
        lat, lon = data.get("latitude"), data.get("longitude")
        if lat is None or lon is None:
            return None
        return float(lat), float(lon)
    except Exception:
        return None


async def _enrich(rec: vlm.Recognition) -> dict:
    center = _district_center(rec.district)
    source = "map search"
    coords = await geo.geocode(rec.location_name, rec.district)

    if not coords and rec.latitude is not None and rec.longitude is not None \
            and geo.in_kerala(rec.latitude, rec.longitude):
        coords, source = (rec.latitude, rec.longitude), "AI estimate"

    if not coords:
        est = await _ai_text_estimate(rec.location_name, rec.district)
        if est and geo.in_kerala(*est) and (center is None or geo.haversine_km(*est, *center) < 80):
            coords, source = est, "AI estimate (approximate)"

    if not coords and center:
        coords, source = center, "district centre (approximate)"

    if not coords:
        raise HTTPException(
            404, f"Could not find '{rec.location_name}' on the map. "
                 "Try the hint as 'Place name, District'.")

    lat, lon = coords
    geo.prefetch_nearby(lat, lon)  # search for nearby places in the background, do not wait for it
    wx = await geo.weather(lat, lon)
    return {
        "status": "ok",
        "recognition": rec.model_dump(),
        "location": {"lat": lat, "lon": lon, "source": source,
                     "approximate": source != "map search"},
        "weather": wx,
        "nearby": [],  # the plan step collects the nearby places itself
    }


def _needs_clarification(file_id: str, rec: vlm.Recognition) -> dict:
    return {
        "status": "needs_clarification",
        "file_id": file_id,
        "recognition": rec.model_dump(),
        "question": "I'm not sure about this one. Type the place name and district, "
                    "for example: Ottathalam Falls, Malappuram",
    }


@app.post("/discover")
async def discover(image: UploadFile = File(...)):
    if not (image.content_type or "").startswith("image/"):
        raise HTTPException(400, "Please upload an image file.")
    raw = await image.read()
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "Image is larger than 10 MB.")
    try:
        jpeg = vlm.preprocess(raw)
    except Exception:
        raise HTTPException(400, "That file could not be read as an image.")
    file_id = uuid.uuid4().hex
    (UPLOADS / f"{file_id}.jpg").write_bytes(jpeg)
    try:
        rec = await vlm.recognize(jpeg)
    except Exception as e:
        raise HTTPException(502, f"Vision model failed: {type(e).__name__}: {e!r}")
    if rec.location_name.lower() == "unknown" or rec.confidence < settings.confidence_threshold:
        return _needs_clarification(file_id, rec)
    return await _enrich(rec)


def _match_known(hint: str) -> vlm.Recognition | None:
    """If the user typed a place from our known list, trust it."""
    lookup = {n.lower(): (n, d, k) for n, d, k in KNOWN_PLACES}
    close = difflib.get_close_matches(hint.split(",")[0].strip().lower(), list(lookup), n=1, cutoff=0.8)
    if not close:
        return None
    name, district, kind = lookup[close[0]]
    return vlm.Recognition(location_name=name, district=district,
                           landmark_type=kind, confidence=1.0)


def _from_hint(hint: str) -> vlm.Recognition:
    """Trust what the user typed: 'Place name, District' or 'Place name District'."""
    parts = [p.strip() for p in hint.split(",") if p.strip()]
    name = parts[0] if parts else hint.strip()
    district = parts[1] if len(parts) > 1 else ""
    if not district:  # no comma? look for a district word inside the text
        for d in DISTRICT_CENTERS:
            if d in name.lower():
                district = d.title()
                name = name.lower().replace(d, "").strip(" ,-").title() or name
                break
    is_fall = any(w in name.lower() for w in ("fall", "aruvi", "kuthu", "para", "kundu", "cascade"))
    return vlm.Recognition(location_name=name, district=district,
                           landmark_type="waterfall" if is_fall else "viewpoint", confidence=0.5)


@app.post("/discover/clarify")
async def clarify(file_id: str = Form(...), hint: str = Form(...)):
    path = UPLOADS / f"{Path(file_id).name}.jpg"
    if not path.exists():
        raise HTTPException(404, "Photo expired. Please upload it again.")
    rec = _match_known(hint)  # 1) a known place: trust it, skip the AI
    if rec is None:
        try:  # 2) ask the AI again, now with the user's hint
            rec = await vlm.recognize(path.read_bytes(), hint=hint)
        except Exception as e:
            print(f"[clarify] AI failed, trusting the user's hint: {type(e).__name__}")
            rec = None
        if rec is None or rec.location_name.lower() == "unknown":
            rec = _from_hint(hint)  # 3) the AI still does not know: trust the typed name
    return await _enrich(rec)


# ---------------- Itinerary (planned by Agno) ----------------
class ItineraryRequest(BaseModel):
    name: str
    district: str = ""
    landmark_type: str = "viewpoint"
    lat: float
    lon: float
    nearby: list[Place] = []


@app.post("/itinerary", response_model=TripState)
async def create_itinerary(req: ItineraryRequest):
    session_id = uuid.uuid4().hex
    nearby = req.nearby or await geo.nearby(req.lat, req.lon)  # usually ready: it started at /discover
    if settings.use_ai_itinerary:
        weather_text = ""
        try:  # the agent uses the weather to decide how long to stay outdoors
            wx = await geo.weather(req.lat, req.lon)
            weather_text = f"{wx['summary']}, {wx['temperature_c']} C, rain {wx['precipitation_mm']} mm"
        except Exception:
            pass
        trip = await build_trip_ai(session_id, req.name, req.district, req.landmark_type,
                                   req.lat, req.lon, nearby, weather_text)
    else:
        trip = await build_trip(session_id, req.name, req.district,
                                req.landmark_type, req.lat, req.lon, nearby)
    store.save(trip)
    return trip

@app.get("/itineraries")
def list_itineraries():
    """The saved routes (from PostgreSQL), newest first."""
    try:
        return db.list_trips()
    except Exception as e:
        print(f"[db] could not list trips: {e}")
        return []


@app.get("/itinerary/{session_id}", response_model=TripState)
def get_itinerary(session_id: str):
    trip = store.load(session_id)
    if not trip:  # not in the live session store: try the saved routes
        try:
            trip = db.get_trip(session_id)
        except Exception:
            trip = None
        if trip:
            store.save(trip)
    if not trip:
        raise HTTPException(404, "Session not found or expired.")
    return trip


@app.post("/itinerary/{session_id}/save")
def save_itinerary(session_id: str):
    trip = store.load(session_id)
    if not trip:
        raise HTTPException(404, "Session not found or expired.")
    try:
        db.save_trip(trip)
    except Exception as e:
        raise HTTPException(503, f"Database unavailable: {e}")
    return {"saved": True}


# ---------------- Plan-editing chatbot (Agno) ----------------
class ChatRequest(BaseModel):
    session_id: str
    message: str


@app.post("/chat")
async def chat(req: ChatRequest):
    trip = store.load(req.session_id)
    if not trip:
        raise HTTPException(404, "Session not found or expired.")
    trip, reply = await agent.replan(trip, req.message.strip()[:500])
    store.save(trip)
    return {"reply": reply, "trip": trip}


# ---------------- Assistant chatbot: budget, guide, friend, anything (Agno Team) ----------------
class AssistantRequest(BaseModel):
    message: str
    session_id: str | None = None  # use the trip's session_id when a plan exists
    place: str = ""                # place name, used when there is no plan yet
    district: str = ""


@app.post("/assistant")
async def assistant(req: AssistantRequest):
    trip = store.load(req.session_id) if req.session_id else None
    key = req.session_id or req.place or "anonymous"
    try:
        from .assistant_agno import ask_assistant
        reply, agent_name = await ask_assistant(
            key, req.message.strip()[:500], trip, req.place, req.district)
    except ImportError as e:
        raise HTTPException(501, f"Agno is not installed in this environment: {e}")
    except Exception as e:
        print(f"[assistant] {type(e).__name__}: {e}")
        raise HTTPException(502, f"Assistant failed: {type(e).__name__}: {e}")
    return {"reply": reply, "agent": agent_name}


# ---------------- Agno check (open /docs and run GET /debug/agno) ----------------
@app.get("/debug/agno")
async def debug_agno():
    from importlib.metadata import PackageNotFoundError, version
    out: dict = {}
    try:
        out["agno_version"] = version("agno")
    except PackageNotFoundError:
        return {"ok": False, "problem": "Agno is not installed in the Python running this server",
                "fix": "pip install -U agno google-genai, then restart the server"}
    try:
        from agno.agent import Agent
        from agno.models.google import Gemini
        from agno.team import Team  # noqa: F401
    except Exception as e:
        return {**out, "ok": False, "problem": f"Import failed: {type(e).__name__}: {e}"}
    try:
        tiny = Agent(model=Gemini(id=settings.gemini_model, api_key=settings.gemini_api_key))
        run = await tiny.arun("Reply with the single word OK")
        out["model_reply"] = str(run.content)[:100]
        out["ok"] = True
    except Exception as e:
        out.update(ok=False, problem=f"Model call failed: {type(e).__name__}: {str(e)[:300]}",
                   hint="Check GEMINI_API_KEY and GEMINI_MODEL in .env, or wait if the quota is used up")
    return out

# ---------------- Find a place by typing its name ----------------
class NameRequest(BaseModel):
    query: str


async def _identify_by_text(query: str) -> vlm.Recognition:
    """The user typed 'Place name' or 'Place name, District'.
    We keep the name they typed and let the AI add the district, the type and rough coordinates."""
    rec = _match_known(query)  # a place from our own list: trust it
    if rec is not None:
        return rec
    base = _from_hint(query)  # the typed name, with a simple guess for district and type
    try:
        data = await ask_json(
            'The user typed this place in Kerala, India: "' + query + '". '
            'Return JSON only with the keys: district (string), landmark_type ("waterfall" or "viewpoint"), '
            "latitude (number or null), longitude (number or null). "
            "Use null when you do not know. Do not guess wildly.")
        if not base.district and data.get("district"):
            base.district = str(data["district"])
        if data.get("landmark_type") in ("waterfall", "viewpoint"):
            base.landmark_type = data["landmark_type"]
        if data.get("latitude") is not None and data.get("longitude") is not None:
            base.latitude = float(data["latitude"])
            base.longitude = float(data["longitude"])
    except Exception as e:  # the AI is only a helper here: the typed name still works without it
        print(f"[by-name] AI details skipped: {type(e).__name__}: {e}")
    return base


@app.post("/discover/by-name")
async def discover_by_name(req: NameRequest):
    query = req.query.strip()[:120]
    if len(query) < 3:
        raise HTTPException(400, "Please type the name of a place (at least 3 letters).")
    rec = await _identify_by_text(query)
    return await _enrich(rec)  # same answer as /discover: place, map pin, weather