import base64
import html
import io
import json
import os
import time
from datetime import date

import requests
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

API = os.getenv("API_URL", "http://localhost:8000")
APP_NAME = "Kerala Hidden Place Finder"
CONTACT_EMAIL = "your-email@example.com"  # change this to your own email

st.set_page_config(page_title=APP_NAME, page_icon="🌴", layout="wide",
                   initial_sidebar_state="collapsed")

ss = st.session_state
DEFAULTS = {"page": "splash", "disc": None, "trip": None, "photo": None, "recent": [],
            "chat_mode": "assistant", "chats": {"assistant": [], "edit": []}, "flash": "",
            "scroll_chat": False}
for _k, _v in DEFAULTS.items():
    ss.setdefault(_k, _v)

POPULAR = [
    {"name": "Athirappilly Falls", "lat": 10.2851, "lon": 76.5698},
    {"name": "Munnar", "lat": 10.0889, "lon": 77.0595},
    {"name": "Vagamon", "lat": 9.6860, "lon": 76.9020},
    {"name": "Chembra Peak", "lat": 11.5167, "lon": 76.0833},
    {"name": "Varkala Cliff", "lat": 8.7333, "lon": 76.7061},
    {"name": "Ponmudi", "lat": 8.7627, "lon": 77.1128},
    {"name": "Thekkady", "lat": 9.6003, "lon": 77.1618},
]
KIND_ICON = {"waterfall": "💧", "viewpoint": "🏞️", "attraction": "📍", "restaurant": "🍽️", "cafe": "☕"}
NAV = [("home", "Home"), ("map", "Map"), ("explore", "Explore"), ("profile", "Profile"), ("contact", "Contact")]

LOGO_SVG = """<svg width="46" height="50" viewBox="0 0 64 70" xmlns="http://www.w3.org/2000/svg">
 <path d="M30 4 C16 4 6 14 6 27 C6 42 30 64 30 64 C30 64 54 42 54 27 C54 14 44 4 30 4Z" fill="#1d3b30"/>
 <path d="M38 58 C36 42 40 32 48 24" stroke="#d6b36a" stroke-width="5" fill="none" stroke-linecap="round"/>
 <path d="M48 24 C38 16 28 20 24 28 M48 24 C46 12 36 8 28 12 M48 24 C56 14 62 16 64 24 M48 24 C58 26 62 34 60 40" stroke="#7aa56e" stroke-width="4" fill="none" stroke-linecap="round"/>
</svg>"""
LOGO_HTML = ('<div class="logo">' + LOGO_SVG + '<div><div class="logo-k">Kerala</div>'
             '<div class="logo-h">HIDDEN PLACE FINDER</div></div></div>')

SCENE_SVG = """<svg viewBox="0 0 1200 260" preserveAspectRatio="xMidYMax slice" xmlns="http://www.w3.org/2000/svg" class="scene">
 <defs>
  <g id="boat"><path d="M0 20 H116 L104 38 H14Z" fill="#7a8f69"/><rect x="14" y="4" width="86" height="16" fill="#d8b47a"/><path d="M8 5 H106 L94 -8 H20Z" fill="#c29858"/></g>
  <g id="palm"><path d="M0 0 C4 -40 -2 -70 6 -100" stroke="#2c4a3b" stroke-width="6" fill="none"/>
   <g fill="#2c4a3b"><ellipse cx="6" cy="-102" rx="34" ry="7" transform="rotate(-28 6 -102)"/><ellipse cx="6" cy="-102" rx="34" ry="7" transform="rotate(26 6 -102)"/>
   <ellipse cx="6" cy="-104" rx="28" ry="6" transform="rotate(-72 6 -104)"/><ellipse cx="6" cy="-104" rx="28" ry="6" transform="rotate(76 6 -104)"/></g></g>
 </defs>
 <path d="M0 172 L140 112 L300 150 L470 92 L640 152 L800 122 L1000 160 L1200 130 L1200 260 L0 260Z" fill="#b9c6a8"/>
 <path d="M520 172 L700 122 L900 152 L1200 112 L1200 260 L520 260Z" fill="#e2bf8c" opacity=".85"/>
 <rect x="0" y="172" width="1200" height="90" fill="#e6e9d4"/>
 <path d="M0 196 C60 150 150 158 230 196 Z" fill="#7f9672"/>
 <path d="M880 204 C960 150 1100 150 1200 192 L1200 220 L880 220Z" fill="#6f8a66"/>
 <use href="#palm" transform="translate(40,190) scale(.45)"/><use href="#palm" transform="translate(95,192) scale(.4)"/>
 <use href="#palm" transform="translate(150,194) scale(.5)"/>
 <use href="#boat" transform="translate(300,196)"/><use href="#boat" transform="translate(820,190) scale(.6)"/>
 <use href="#palm" transform="translate(1010,206) scale(1.3)"/><use href="#palm" transform="translate(1090,208) scale(1.6)"/>
 <use href="#palm" transform="translate(1160,210) scale(1.25)"/>
</svg>"""

CSS = """
<style>
#MainMenu, footer, header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display:none !important;}
[data-testid="stAppViewContainer"] {background:#faf8f3;}
[data-testid="stMainBlockContainer"], .block-container {max-width:100% !important; padding:0 !important;}
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {gap:0 !important;}
body, .stApp, .stMarkdown, .stButton button, input, textarea {font-family:"Segoe UI", system-ui, sans-serif;}

.st-key-topbar {background:#e8ebd3; padding:10px max(24px, calc((100vw - 1180px)/2)) !important; gap:0 !important;}
.st-key-topbar [data-testid="stHorizontalBlock"] {align-items:center;}
.st-key-topbar button {border:0 !important; background:transparent !important; box-shadow:none !important;
  color:#1d3b30 !important; font-weight:500 !important; padding:.4rem .5rem !important; min-height:0 !important;}
.st-key-topbar button[kind="primary"], .st-key-topbar button[data-testid="stBaseButton-primary"] {
  background:#1d3b30 !important; color:#fff !important; border-radius:10px !important;}
.logo {display:flex; align-items:center; gap:10px;}
.logo-k {font-family:Georgia,'Times New Roman',serif; font-size:30px; color:#1d3b30; line-height:1;}
.logo-h {font-size:12px; letter-spacing:1.5px; color:#1d3b30; margin-top:2px;}

.hero {padding:32px max(24px, calc((100vw - 1180px)/2)) 62px;
  background: radial-gradient(circle at 85% 20%, rgba(255,255,255,.10), transparent 40%),
              linear-gradient(120deg,#143f34 0%,#1f6f5c 55%,#2c8a78 100%); color:#fff;}
.hs {font-size:18px; opacity:.92;} .ht {font-size:34px; font-weight:700; margin-top:2px;}
.sheet-top {height:36px; margin-top:-36px; background:#faf8f3; border-radius:36px 36px 0 0; position:relative;}

.st-key-body {max-width:1180px; margin:0 auto; padding:0 24px 120px !important; width:100%; box-sizing:border-box;}
.sec {font-size:21px; font-weight:700; color:#16231d; margin:14px 0 8px;}
.card {background:#fff; border-radius:18px; box-shadow:0 2px 12px rgba(0,0,0,.08); padding:14px 18px; margin-bottom:10px;}
.upl {display:flex; align-items:center; gap:14px; background:#fff; border-radius:18px; padding:12px 16px;
  box-shadow:0 2px 12px rgba(0,0,0,.08); font-size:16px; color:#16231d;}
.upl-i {width:46px; height:46px; border-radius:12px; background:linear-gradient(135deg,#1f6f5c,#2c8a78); color:#fff;
  display:flex; align-items:center; justify-content:center; font-size:22px;}
.upl span {color:#5c6b63;}
.badge {display:inline-block; background:#e3f2e9; color:#14573a; padding:4px 10px; border-radius:999px; font-size:13px; margin:0 6px 6px 0;}
.warn {background:#fff4d6; color:#7a5200; padding:8px 12px; border-radius:10px; font-size:13px; margin:6px 0;}
.week {display:flex; justify-content:space-between; margin-top:12px;}
.wd {text-align:center; font-size:11px; color:#8a958f; flex:1;}
.wd i {display:block; width:9px; height:9px; border-radius:50%; background:#d4dad6; margin:0 auto 4px;}
.wd.on i {background:#2c8a78;} .wd.now i {width:13px; height:13px; margin-top:-2px; box-shadow:0 0 0 3px #cfe6df;}
.wd.now {color:#16231d; font-weight:700;}
.rgrid {display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr)); gap:14px;}
.rc {background:#fff; border-radius:16px; box-shadow:0 2px 10px rgba(0,0,0,.09); padding:8px;}
.rc img, .rc .ph {width:100%; height:100px; object-fit:cover; border-radius:12px; background:#dbe7e1; display:block;}
.rc .ph {display:flex; align-items:center; justify-content:center; font-size:34px;}
.rn {font-weight:700; font-size:14px; margin-top:6px; color:#16231d;} .rm {font-size:12px; color:#6a766f;}
.stopcard {display:flex; gap:12px; background:#fff; border-radius:16px; padding:12px 14px;
  box-shadow:0 2px 10px rgba(0,0,0,.07); border-left:5px solid #2c8a78;}
.stopcard.indoor {border-left-color:#d08a2a;} .stopcard .t {font-weight:700; color:#1f6f5c; min-width:48px;}
.stopcard small {color:#6a766f;}
.leg {color:#7b867f; font-size:12px; margin:4px 0 4px 20px;}
.recgrid {display:grid; grid-template-columns:repeat(auto-fill,minmax(250px,1fr)); gap:10px;}
.rec {display:flex; gap:12px; background:#fffaf0; border:1px solid #f0dfb8; border-radius:16px; padding:12px 14px;}
.rec .ri {font-size:22px;} .rec span {color:#6a5a30; font-size:13px;}
.note {font-size:12px; color:#7b867f; margin-top:6px;}
.scene {width:100%; height:230px; display:block; border-radius:18px; margin-top:14px;}

.stButton > button {border-radius:14px; border:1px solid #d9e2dc; background:#fff; color:#17483b; font-weight:600; padding:.5rem 1rem;}
.stButton > button[kind="primary"], .stButton > button[data-testid="stBaseButton-primary"] {
  background:linear-gradient(135deg,#1f6f5c,#2c8a78); color:#fff; border:0;}
[data-testid="stFileUploaderDropzone"] {border-radius:16px; background:#fff; border:1.5px dashed #8fbfb2;}
[data-testid="stFormSubmitButton"] button {border-radius:14px; font-weight:600;}
[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"],
[data-testid="stFormSubmitButton"] button[data-testid="stBaseButton-primaryFormSubmit"] {
  background:linear-gradient(135deg,#1f6f5c,#2c8a78); color:#fff; border:0;}
.stTabs [data-baseweb="tab"] {font-weight:600;}

.st-key-explore_btn {position:relative; margin-top:-62px; z-index:5; display:flex; flex-direction:row-reverse; padding-right:22px;}
.st-key-explore_btn button {background:#fff !important; border-radius:999px !important; box-shadow:0 2px 10px rgba(0,0,0,.2) !important; border:0 !important;}
.st-key-fabs {position:fixed; bottom:26px; right:26px; z-index:1000; width:56px;}
.st-key-fabs button {width:54px !important; height:54px !important; min-height:54px !important; border-radius:50% !important;
  padding:0 !important; font-size:22px !important; border:0 !important; box-shadow:0 4px 12px rgba(0,0,0,.28) !important; margin-bottom:8px;}
.st-key-fab_chat button {background:#1f8a78 !important; color:#fff !important;}
.st-key-fab_edit button {background:#4b78a8 !important; color:#fff !important;}
.st-key-chatbox {background:#fff; border-radius:20px; box-shadow:0 2px 12px rgba(0,0,0,.08); padding:16px 18px; margin-top:14px;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

SPLASH = ("""
<style>
[data-testid="stAppViewContainer"] {background:#eceed8 !important;}
.sp-nav {display:flex; justify-content:space-between; align-items:center; padding:18px max(24px, calc((100vw - 1180px)/2));}
.sp-nav .links {display:flex; gap:28px; color:#1d3b30; font-size:15px;}
.sp {text-align:center; padding:48px 0 0;}
.sp-k {font-family:Georgia,'Times New Roman',serif; font-size:80px; color:#1d3b30; line-height:1.05;}
.sp-h {font-size:46px; letter-spacing:2px; color:#1d3b30; line-height:1.2; margin-top:10px;}
.sp-t {font-size:19px; color:#46584f; margin:16px 0 30px;}
.sp .scene {border-radius:0; height:270px;}
.spin {width:26px; height:26px; border:3px dotted #8d9a8f; border-radius:50%; margin:14px auto 6px; animation:sp 1.4s linear infinite;}
@keyframes sp {to {transform:rotate(360deg);}}
.sp-f {font-size:14px; color:#46584f;}
</style>
<div class="sp-nav">""" + LOGO_HTML + """<div class="links"><span>Home</span><span>Explore</span><span>Maps</span><span>About Us</span><span>Contact</span></div></div>
<div class="sp">
<div class="sp-k">Kerala</div>
<div class="sp-h">HIDDEN PLACE<br>FINDER</div>
<div class="sp-t">Explore the unseen.</div>
""" + SCENE_SVG + """
<div class="spin"></div>
<div class="sp-f">Discover the unseen Kerala</div>
</div>
""")

MAP_HTML = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
html,body{margin:0;height:100%;font-family:system-ui,Segoe UI,sans-serif;background:transparent}
#map{position:absolute;inset:0;border-radius:22px;background:#dfe9e4}
.pin{width:28px;height:28px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);border:2px solid #fff;
 box-shadow:0 2px 6px rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center}
.pin b{transform:rotate(45deg);color:#fff;font-size:12px}
.dotpin{width:12px;height:12px;border-radius:50%;background:#7fa08f;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.3)}
.legend{position:absolute;left:10px;bottom:10px;z-index:1000;background:rgba(255,255,255,.93);border-radius:12px;
 padding:6px 10px;font-size:11px;line-height:1.55;box-shadow:0 1px 6px rgba(0,0,0,.2)}
.legend i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:middle}
.pop b{display:block;margin-bottom:2px}.pop span{color:#555;font-size:12px}
</style></head><body>
<div id="map"></div><div class="legend" id="legend"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const D = __DATA__;
const map = L.map("map");
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",
  {maxZoom: 19, attribution: "© OpenStreetMap contributors"}).addTo(map);
const pts = [];
function icon(color, text) {
  return L.divIcon({className: "", html: '<div class="pin" style="background:' + color + '"><b>' + text + "</b></div>",
    iconSize: [28, 28], iconAnchor: [14, 30], popupAnchor: [0, -28]});
}
function popup(title, sub) {
  const d = document.createElement("div"); d.className = "pop";
  const b = document.createElement("b"); b.textContent = title; d.appendChild(b);
  if (sub) { const s = document.createElement("span"); s.textContent = sub; d.appendChild(s); }
  return d;
}
function add(p, ic, title, sub) {
  L.marker([p.lat, p.lon], {icon: ic}).addTo(map).bindPopup(popup(title, sub));
  pts.push([p.lat, p.lon]);
}
if (D.stops.length > 1) {
  L.polyline(D.stops.map(s => [s.lat, s.lon]),
    {color: "#1f6f5c", weight: 3, opacity: .7, dashArray: "6 8"}).addTo(map);
}
D.stops.forEach((s, i) => add(s, i === 0 ? icon("#d93025", "★") : icon("#1f6f5c", String(s.n)),
  s.n + ". " + s.name, s.start + " · " + s.kind));
if (D.main && !D.stops.length) add(D.main, icon("#d93025", "★"), D.main.name, "Your place");
D.recs.forEach(r => add(r, icon("#e8a317", "★"), r.name, r.reason));
if (!pts.length) {
  D.popular.forEach(p => {
    L.marker([p.lat, p.lon], {icon: L.divIcon({className: "", html: '<div class="dotpin"></div>', iconSize: [12, 12]})})
      .addTo(map).bindPopup(popup(p.name, "Popular place"));
    pts.push([p.lat, p.lon]);
  });
}
if (pts.length > 1) map.fitBounds(pts, {padding: [40, 40], maxZoom: 13});
else if (pts.length === 1) map.setView(pts[0], 12);
else map.setView([10.3, 76.4], 7);
const leg = [];
if (D.main || D.stops.length) leg.push('<div><i style="background:#d93025"></i>Your place</div>');
if (D.stops.length > 1) leg.push('<div><i style="background:#1f6f5c"></i>Day plan (numbered)</div>');
if (D.recs.length) leg.push('<div><i style="background:#e8a317"></i>Recommended places</div>');
if (!D.main && !D.stops.length) leg.push('<div><i style="background:#7fa08f"></i>Popular places</div>');
document.getElementById("legend").innerHTML = leg.join("");
</script></body></html>"""


# ---------------- helpers ----------------
def esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


def call(method: str, path: str, **kw):
    try:
        r = requests.request(method, f"{API}{path}", timeout=240, **kw)
    except requests.RequestException:
        st.error("Cannot reach the backend. Is it running on port 8000?")
        return None
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail", r.text)
        except ValueError:
            detail = r.text
        st.error(f"Error {r.status_code}: {detail}")
        return None
    return r.json()


def go(page: str):
    ss.page = page



def set_mode(mode: str):
    ss.chat_mode = mode


def make_thumb(data: bytes) -> str:
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img.thumbnail((320, 240))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=70)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


def remember(disc: dict, data: bytes):
    rec = disc["recognition"]
    ss.recent = [r for r in ss.recent if r["name"] != rec["location_name"]]
    ss.recent.insert(0, {"name": rec["location_name"], "district": rec["district"],
                         "kind": rec["landmark_type"], "thumb": make_thumb(data)})
    ss.recent = ss.recent[:8]


def hero(sub: str, title: str):
    st.markdown(f'<div class="hero"><div class="hs">{esc(sub)}</div><div class="ht">{title}</div></div>'
                '<div class="sheet-top"></div>', unsafe_allow_html=True)


def sec(title: str):
    st.markdown(f'<div class="sec">{esc(title)}</div>', unsafe_allow_html=True)


def map_data() -> dict:
    trip, disc = ss.trip, ss.disc
    data = {"main": None, "stops": [], "recs": [], "popular": POPULAR}
    if trip:
        for i, s in enumerate(trip["stops"], 1):
            data["stops"].append({"n": i, "lat": s["lat"], "lon": s["lon"], "name": s["name"],
                                  "start": s["start"], "kind": s["kind"]})
        for r in trip.get("recommendations", []):
            data["recs"].append({"lat": r["lat"], "lon": r["lon"], "name": r["name"],
                                 "reason": r.get("reason", "")})
    elif disc and disc.get("status") == "ok":
        loc = disc["location"]
        data["main"] = {"lat": loc["lat"], "lon": loc["lon"], "name": disc["recognition"]["location_name"]}
        for p in [p for p in disc.get("nearby", []) if p["kind"] == "attraction"][:6]:
            data["recs"].append({"lat": p["lat"], "lon": p["lon"], "name": p["name"], "reason": "Nearby place"})
    return data


def show_map(height: int):
    payload = json.dumps(map_data()).replace("</", "<\\/")
    components.html(MAP_HTML.replace("__DATA__", payload), height=height)


def week_strip() -> str:
    today = date.today().weekday()
    cells = ""
    for i, d in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
        cls = "wd"
        if i <= today:
            cls += " on"
        if i == today:
            cls += " now"
        cells += f'<div class="{cls}"><i></i>{d}</div>'
    return f'<div class="week">{cells}</div>'


def recent_cards() -> str:
    if not ss.recent:
        return '<div class="card" style="color:#6a766f">Places you find will appear here. Upload your first photo.</div>'
    cards = ""
    for r in ss.recent:
        img = f'<img src="{r["thumb"]}">' if r["thumb"] else '<div class="ph">🌴</div>'
        cards += (f'<div class="rc">{img}<div class="rn">{esc(r["name"])}</div>'
                  f'<div class="rm">📍 {esc(r["district"])} · {esc(r["kind"])}</div></div>')
    return f'<div class="rgrid">{cards}</div>'


def timeline_html(trip: dict) -> str:
    out = ""
    for s in trip["stops"]:
        leg = s.get("leg_from_prev")
        if leg:
            out += f'<div class="leg">↓ {leg["distance_km"]} km · about {round(leg["duration_min"])} min drive</div>'
        cls = "stopcard" + ("" if s["outdoor"] else " indoor")
        out += (f'<div class="{cls}"><div class="t">{esc(s["start"])}</div><div><b>{esc(s["name"])}</b><br>'
                f'<small>{KIND_ICON.get(s["kind"], "📍")} {esc(s["kind"])} · {s["duration_min"]} min</small></div></div>')
    return out


def recs_html(trip: dict) -> str:
    cards = ""
    for r in trip.get("recommendations", []):
        cards += (f'<div class="rec"><div class="ri">⭐</div><div><b>{esc(r["name"])}</b> '
                  f'<small>· {r["distance_km"]} km away</small><br><span>{esc(r["reason"])}</span></div></div>')
    return f'<div class="recgrid">{cards}</div>' if cards else ""


def plan_panel(prefix: str):
    """The one-day plan. It is shown on the page the moment the plan is created."""
    trip = ss.trip
    sec("Your one-day plan")
    if trip.get("summary"):
        st.markdown(f'<div class="card" style="color:#2f4a3f">{esc(trip["summary"])}</div>', unsafe_allow_html=True)
    for w in trip.get("warnings", []):
        st.markdown(f'<div class="warn">{esc(w)}</div>', unsafe_allow_html=True)
    st.markdown(timeline_html(trip), unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("💾 Save plan", key=f"{prefix}_save"):
        if call("POST", f"/itinerary/{trip['session_id']}/save"):
            st.success("Plan saved. Find it under Profile > My Saved Routes.")
    c2.button("✏️ Edit with chat", key=f"{prefix}_edit", on_click=open_chat, args=("edit",))


def new_plan_state():
    ss.trip = None
    ss.chats = {"assistant": [], "edit": []}


def reset_all():
    new_plan_state()
    ss.disc = None
    ss.photo = None


# ---------------- pages ----------------
def page_splash():
    st.markdown(SPLASH, unsafe_allow_html=True)
    _, mid, _ = st.columns([2, 1, 2])
    mid.button("Start exploring  →", key="start", type="primary", on_click=go, args=("home",))
    time.sleep(3)
    if ss.page == "splash":
        ss.page = "home"
        st.rerun()


def home_left():
    sec("Quick Actions")
    tab_photo, tab_name = st.tabs(["📷 Upload photo", "⌨️ Type place name"])

    up = None
    with tab_photo:
        st.markdown('<div class="upl"><div class="upl-i">⬆</div><div><b>Upload Screenshot / Image</b><br>'
                    '<span>to Find Location</span></div></div>', unsafe_allow_html=True)
        up = st.file_uploader("photo", type=["jpg", "jpeg", "png", "webp"], label_visibility="collapsed")
        if up:
            sig = f"{up.name}-{up.size}"
            if ss.photo != sig:  # a new photo: start again
                ss.photo, ss.disc = sig, None
                new_plan_state()
            st.image(up, width=220)
            if st.button("🔍 Find this place", type="primary", key="find"):
                with st.spinner("Looking at your photo..."):
                    data = call("POST", "/discover",
                                files={"image": (up.name, up.getvalue(), up.type or "image/jpeg")})
                if data:
                    ss.disc = data
                    if data["status"] == "ok":
                        remember(data, up.getvalue())
                    st.rerun()

    with tab_name:
        st.markdown('<div class="upl"><div class="upl-i">⌨</div><div><b>Type the name of a place</b><br>'
                    '<span>Example: Ottathalam Falls, Malappuram</span></div></div>', unsafe_allow_html=True)
        with st.form("name_form"):
            query = st.text_input("Place name", label_visibility="collapsed",
                                  placeholder="Place name, District (the district is optional)")
            by_name = st.form_submit_button("🔎 Find this place", type="primary")
        if by_name:
            if len(query.strip()) < 3:
                st.warning("Please type at least 3 letters.")
            else:
                with st.spinner("Looking for the place..."):
                    data = call("POST", "/discover/by-name", json={"query": query.strip()})
                if data:
                    ss.disc = data
                    new_plan_state()
                    remember(data, b"")
                    st.rerun()

    disc = ss.disc
    if disc and disc["status"] == "needs_clarification":
        st.markdown(f'<div class="warn">{esc(disc["question"])}</div>', unsafe_allow_html=True)
        hint = st.text_input("Place name, District", key="hint", placeholder="Ottathalam Falls, Malappuram")
        if st.button("Retry with this place", key="retry") and hint.strip() and up:
            with st.spinner("Looking it up..."):
                data = call("POST", "/discover/clarify",
                            data={"file_id": disc["file_id"], "hint": hint.strip()})
            if data:
                data["file_id"] = disc["file_id"]
                ss.disc = data
                remember(data, up.getvalue())
                st.rerun()

    if disc and disc["status"] == "ok":
        rec, loc, wx = disc["recognition"], disc["location"], disc["weather"]
        badges = [rec["district"], rec["landmark_type"], wx["summary"], f"{wx['temperature_c']}°C",
                  f"wind {wx['wind_kmh']} km/h", f"rain {wx['precipitation_mm']} mm"]
        pills = "".join(f'<span class="badge">{esc(b)}</span>' for b in badges if b)
        warn = ""
        if loc.get("approximate"):
            warn = f'<div class="warn">The map pin is approximate ({esc(loc.get("source"))}). Check it before you travel.</div>'
        st.markdown(f'<div class="card"><div style="font-size:19px;font-weight:700">{esc(rec["location_name"])}</div>'
                    f'{pills}{warn}</div>', unsafe_allow_html=True)
        if st.button("✨ Create my 1-day plan", type="primary", key="plan"):
            body = {"name": rec["location_name"], "district": rec["district"],
                    "landmark_type": rec["landmark_type"], "lat": loc["lat"], "lon": loc["lon"],
                    "nearby": disc.get("nearby", [])}
            with st.status("Creating your one-day plan...", expanded=True) as status:
                st.write(f"📍 Finding places to visit and eat near {rec['location_name']}")
                st.write("🤖 The Agno planner is choosing your stops. This can take up to a minute.")
                trip = call("POST", "/itinerary", json=body)
                status.update(label="Your plan is ready!" if trip else "Could not create the plan",
                              state="complete" if trip else "error")
            if trip:
                ss.trip = trip
                ss.chats = {"assistant": [], "edit": []}
                ss.flash = "Your 1-day plan is ready! You can see it below and on the map."
                st.rerun()

    if ss.trip:  # the plan appears right here, under the button, the moment it is created
        plan_panel("home")

    sec("Itinerary Planner")
    st.markdown('<div class="card"><div style="font-size:18px;font-weight:700">Plan Your<br>Hidden Journey</div>'
                + week_strip() + "</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.button("➕ Create New", key="create_new", on_click=reset_all)
    c2.button("🔖 My Saved Routes", key="saved_routes", on_click=go, args=("profile",))
    if not ss.trip:
        st.markdown(SCENE_SVG, unsafe_allow_html=True)


CHAT_SCROLL_JS = """<script>
const goChat = () => {
  const el = window.parent.document.querySelector('.st-key-chatbox');
  if (el) el.scrollIntoView({behavior: 'smooth', block: 'start'});
};
setTimeout(goChat, 150);
setTimeout(goChat, 700);
</script>"""


def open_chat(mode: str):
    """The chat lives on the Home page. The round buttons switch the mode and jump to it."""
    ss.chat_mode = mode
    ss.page = "home"
    ss.scroll_chat = True


def chat_box():
    """Both chatbots (assistant and plan editor) live here, on the Home page under Recent Discoveries."""
    with st.container(key="chatbox"):
        st.markdown('<div class="sec" style="margin-top:0">💬 Chat with your planner</div>', unsafe_allow_html=True)
        mode = ss.chat_mode
        trip, disc = ss.trip, ss.disc
        c1, c2 = st.columns(2)
        c1.button("💬 Ask the assistant", key="m_a", on_click=set_mode, args=("assistant",),
                  type="primary" if mode == "assistant" else "secondary")
        c2.button("✏️ Edit my plan", key="m_e", on_click=set_mode, args=("edit",),
                  type="primary" if mode == "edit" else "secondary")

        if mode == "edit" and not trip:
            st.markdown('<div class="note">Create a 1-day plan first, then you can edit it here.</div>',
                        unsafe_allow_html=True)
        else:
            if mode == "assistant":
                st.markdown('<div class="note">Ask about the budget, the place, safety, or just chat. '
                            'Try: How much will this trip cost for 4 people?</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="note">Try: Spend 2 hours at the first stop · Remove the last stop · '
                            "It's raining, replace the waterfall with a cafe</div>", unsafe_allow_html=True)
            with st.form("chat_form", clear_on_submit=True):
                text = st.text_input("Message", placeholder="Type your message...", label_visibility="collapsed")
                sent = st.form_submit_button("Send", type="primary")
            if sent and text.strip():
                with st.spinner("Thinking..."):
                    if mode == "edit":
                        data = call("POST", "/chat", json={"session_id": trip["session_id"], "message": text.strip()})
                        if data:
                            ss.trip = data["trip"]  # the plan and the map above update at once
                            ss.chats["edit"].append({"q": text.strip(), "a": data["reply"]})
                    else:
                        rec = disc["recognition"] if disc and disc.get("status") == "ok" else {}
                        data = call("POST", "/assistant", json={
                            "message": text.strip(),
                            "session_id": trip["session_id"] if trip else None,
                            "place": trip["destination"] if trip else rec.get("location_name", ""),
                            "district": trip["district"] if trip else rec.get("district", "")})
                        if data:
                            ss.chats["assistant"].append({"q": text.strip(), "a": data["reply"]})
                ss.scroll_chat = True  # stay on the chat after the page refreshes
                st.rerun()
            for ex in reversed(ss.chats[mode]):  # newest first, so you never have to scroll
                st.chat_message("user").write(ex["q"])
                st.chat_message("assistant").write(ex["a"])

    if ss.scroll_chat:
        components.html(CHAT_SCROLL_JS, height=0)
        ss.scroll_chat = False


def home_right():
    sec("Hidden Places Map")
    show_map(340)
    with st.container(key="explore_btn"):
        st.button("Explore Live Map", key="live_map", on_click=go, args=("map",))
    if ss.trip and ss.trip.get("recommendations"):
        sec("⭐ Also worth visiting")
        st.markdown(recs_html(ss.trip), unsafe_allow_html=True)
    sec("Recent Discoveries")
    st.markdown(recent_cards(), unsafe_allow_html=True)
    chat_box()


def page_home():
    hero("Welcome to", "📍 Discover Hidden Kerala")
    with st.container(key="body"):
        if ss.flash:
            st.success(ss.flash)
            ss.flash = ""
        left, right = st.columns([1, 1.8], gap="large")
        with left:
            home_left()
        with right:
            home_right()


def page_map():
    hero("Explore", "🗺️ Live Map")
    with st.container(key="body"):
        if not (ss.trip or (ss.disc and ss.disc.get("status") == "ok")):
            st.markdown('<div class="note">Popular places are shown. Find a place on Home to see your own plan here.</div>',
                        unsafe_allow_html=True)
        show_map(560)
        st.markdown('<div class="note">Red star = your place · numbers = your day plan · gold stars = recommended places.'
                    ' Click a pin to see details.</div>', unsafe_allow_html=True)


def page_explore():
    hero("Your day", "🧭 Plan and recommendations")
    with st.container(key="body"):
        trip = ss.trip
        if not trip:
            st.markdown('<div class="card">No plan yet. Go to Home, upload a photo and click '
                        '<b>Create my 1-day plan</b>.</div>', unsafe_allow_html=True)
            return
        left, right = st.columns([1, 1.3], gap="large")
        with left:
            st.markdown(f'<div class="sec">{esc(trip["destination"])}</div>', unsafe_allow_html=True)
            plan_panel("explore")
        with right:
            sec("Map")
            show_map(380)
            if trip.get("recommendations"):
                sec("⭐ Also worth visiting")
                st.markdown(recs_html(trip), unsafe_allow_html=True)




def page_profile():
    hero("Profile", "👤 " + APP_NAME)
    with st.container(key="body"):
        left, right = st.columns([1.3, 1], gap="large")
        with left:
            sec("My Saved Routes")
            routes = call("GET", "/itineraries") or []
            if not routes:
                st.markdown('<div class="card" style="color:#6a766f">No saved routes yet. Open a plan and click '
                            '<b>Save plan</b>.</div>', unsafe_allow_html=True)
            for r in routes:
                a, b = st.columns([4, 1])
                a.markdown(f'<div class="card"><b>{esc(r["destination"])}</b><br>'
                           f'<small>{esc(r["updated_at"][:10])}</small></div>', unsafe_allow_html=True)
                if b.button("Open", key=f"open_{r['session_id']}"):
                    trip = call("GET", f"/itinerary/{r['session_id']}")
                    if trip:
                        ss.trip, ss.disc = trip, None
                        ss.chats = {"assistant": [], "edit": []}
                        ss.page = "explore"
                        st.rerun()
        with right:
            sec("About")
            st.markdown('<div class="card">Upload a photo of a waterfall or viewpoint, and get a full-day plan, '
                        'a map with recommended places, and an AI assistant for budget, place guide and friendly chat.'
                        '<br><span class="note">AI answers can be wrong. Check prices, timings and safety locally.</span></div>',
                        unsafe_allow_html=True)


def page_contact():
    hero("Contact", "✉️ Get in touch")
    with st.container(key="body"):
        st.markdown(f'<div class="card"><b>{esc(APP_NAME)}</b><br>Questions, feedback or a place we should add?<br>'
                    f'Write to <b>{esc(CONTACT_EMAIL)}</b></div>', unsafe_allow_html=True)


def topbar():
    with st.container(key="topbar"):
        c_logo, c_nav = st.columns([5, 6])
        c_logo.markdown(LOGO_HTML, unsafe_allow_html=True)
        for col, (pid, label) in zip(c_nav.columns(len(NAV)), NAV):
            col.button(label, key=f"nav_{pid}", on_click=go, args=(pid,),
                       type="primary" if ss.page == pid else "secondary")


def fabs():
    with st.container(key="fabs"):
        st.button("💬", key="fab_chat", on_click=open_chat, args=("assistant",), help="Ask the assistant")
        st.button("✏️", key="fab_edit", on_click=open_chat, args=("edit",), help="Edit my plan")


# ---------------- router ----------------
if ss.page == "splash":
    page_splash()
    st.stop()

topbar()
{"home": page_home, "map": page_map, "explore": page_explore,
 "profile": page_profile, "contact": page_contact}.get(ss.page, page_home)()
fabs()