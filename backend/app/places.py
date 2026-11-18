"""Known Kerala waterfalls and viewpoints, and district centres.

KNOWN_PLACES: (name, district, type). Add your own places here.
More places means better recognition. Please verify names on Google Maps.
"""

KNOWN_PLACES = [
    ("Athirappilly Falls", "Thrissur", "waterfall"),
    ("Vazhachal Falls", "Thrissur", "waterfall"),
    ("Meenmutty Falls", "Wayanad", "waterfall"),
    ("Soochipara Falls", "Wayanad", "waterfall"),
    ("Kanthanpara Falls", "Wayanad", "waterfall"),
    ("Chembra Peak", "Wayanad", "viewpoint"),
    ("Lakkidi View Point", "Wayanad", "viewpoint"),
    ("Neelimala View Point", "Wayanad", "viewpoint"),
    ("Keralamkundu Waterfalls", "Malappuram", "waterfall"),
    ("Thusharagiri Falls", "Kozhikode", "waterfall"),
    ("Aruvikkuzhi Falls", "Kottayam", "waterfall"),
    ("Marmala Falls", "Kottayam", "waterfall"),
    ("Palaruvi Falls", "Kollam", "waterfall"),
    ("Thommankuthu Falls", "Idukki", "waterfall"),
    ("Cheeyappara Waterfalls", "Idukki", "waterfall"),
    ("Valara Waterfalls", "Idukki", "waterfall"),
    ("Meenvallam Falls", "Palakkad", "waterfall"),
    ("Ramakkalmedu", "Idukki", "viewpoint"),
    ("Kolukkumalai", "Idukki", "viewpoint"),
    ("Top Station Munnar", "Idukki", "viewpoint"),
    ("Echo Point Munnar", "Idukki", "viewpoint"),
    ("Vagamon Meadows", "Idukki", "viewpoint"),
    ("Ilaveezhapoonchira", "Kottayam", "viewpoint"),
    ("Ponmudi", "Thiruvananthapuram", "viewpoint"),
    ("Varkala Cliff", "Thiruvananthapuram", "viewpoint"),
]

# Approximate centre of each Kerala district: (latitude, longitude).
# Used as a last-resort pin when a hidden place is not on the map.
DISTRICT_CENTERS = {
    "thiruvananthapuram": (8.5241, 76.9366),
    "kollam": (8.8932, 76.6141),
    "pathanamthitta": (9.2648, 76.7870),
    "alappuzha": (9.4981, 76.3388),
    "kottayam": (9.5916, 76.5222),
    "idukki": (9.8494, 76.9710),
    "munnar": (10.0889, 77.0595),
    "ernakulam": (9.9816, 76.2999),
    "thrissur": (10.5276, 76.2144),
    "palakkad": (10.7867, 76.6548),
    "malappuram": (11.0510, 76.0711),
    "kozhikode": (11.2588, 75.7804),
    "wayanad": (11.6854, 76.1320),
    "kannur": (11.8745, 75.3704),
    "kasaragod": (12.4996, 74.9869),
}


def candidates_text() -> str:
    return "; ".join(f"{n} ({d})" for n, d, _ in KNOWN_PLACES)