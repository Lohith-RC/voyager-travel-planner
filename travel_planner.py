import os
import re
import json
import math
import random
import hashlib
import urllib.request
import urllib.parse
from urllib.parse import quote
from xml.sax.saxutils import escape
import pandas as pd
import pydeck as pdk
import streamlit as st
from groq import Groq
from dotenv import load_dotenv
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
from datetime import datetime

# ---------------- CONFIG ----------------
st.set_page_config(
    page_title="Voyager — Smart Travel Planner",
    layout="wide",
    page_icon="✦"
)

# ---------------- LOAD API ----------------
load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")

client = None
if groq_api_key:
    client = Groq(api_key=groq_api_key)

# ---------------- SECURITY HELPERS ----------------
MAX_LOCATION_LEN = 80


def clean_location(value):
    """Sanitize free-text input: drop control chars, allow only safe name
    characters, trim, and cap length. Prevents markup injection in any
    downstream HTML/rendering context."""
    if not value:
        return ""
    value = re.sub(r"[\x00-\x1f\x7f]", "", str(value))
    value = re.sub(r"[^\w\s.,'()/\-]", "", value)
    return value.strip()[:MAX_LOCATION_LEN]


def h(value):
    """HTML-escape untrusted values before interpolating into raw HTML blocks."""
    return escape(str(value), {'"': "&quot;", "'": "&#x27;"})


def safe_filename(value, fallback="trip"):
    """Build a filesystem-safe filename fragment from user input."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "")).strip("._-")
    return cleaned[:60] or fallback


MEMORY_FILE = "travel_memory.json"

# ---------------- MEMORY ----------------
def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    return {}

def save_memory(from_location, destination, interests, dates, budget):
    memory = {
        "last_from": from_location,
        "last_destination": destination,
        "last_interests": interests,
        "last_dates": dates,
        "last_budget": budget,
        "timestamp": datetime.now().isoformat()
    }
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=4)

# ---------------- MOCK DATA ----------------
FLIGHT_OPTIONS = [
    {"Airline": "IndiGo", "Base Price": 4500, "Duration": "2h 15m", "Stops": "Non-stop"},
    {"Airline": "Air India", "Base Price": 5500, "Duration": "2h 30m", "Stops": "Non-stop"},
    {"Airline": "Vistara", "Base Price": 6200, "Duration": "2h 45m", "Stops": "1 Stop"},
    {"Airline": "Akasa Air", "Base Price": 4100, "Duration": "2h 20m", "Stops": "Non-stop"},
    {"Airline": "SpiceJet", "Base Price": 3800, "Duration": "2h 55m", "Stops": "1 Stop"},
]

HOTEL_OPTIONS = [
    {"Hotel Name": "Budget Nest Inn", "Stars": 3.6, "Base Price/Day": 1800, "Area": "Near Airport"},
    {"Hotel Name": "Grand Palace Hotel", "Stars": 4.2, "Base Price/Day": 3200, "Area": "City Center"},
    {"Hotel Name": "Tranquil Boutique Stay", "Stars": 4.5, "Base Price/Day": 4200, "Area": "Old Town"},
    {"Hotel Name": "Riverside Resort", "Stars": 4.7, "Base Price/Day": 5200, "Area": "Lakeside"},
]

ATTRACTION_DB = {
    "nature": [("Lake View Point", "🌿"), ("National Park", "🌳"), ("Botanical Garden", "🌸")],
    "food": [("Food Street", "🍜"), ("Cafe Tour", "☕"), ("Local Restaurant", "🍽")],
    "history": [("Heritage Museum", "🏛"), ("Ancient Fort", "🏰"), ("Old Temple", "🛕")],
    "adventure": [("Hill Trekking", "⛰️"), ("White-water Boating", "🚣"), ("Adventure Park", "🎢")],
}


def _seed_for(from_location, destination):
    key = f"{from_location.strip().lower()}->{destination.strip().lower()}"
    return int(hashlib.md5(key.encode()).hexdigest(), 16) % (2 ** 32)


def search_flights(from_location, destination):
    rng = random.Random(_seed_for(from_location, destination))
    flights = []
    for template in FLIGHT_OPTIONS:
        price = max(template["Base Price"] + rng.randint(-700, 1400), 1500)
        flights.append({**template, "Price (₹)": price})
    flights.sort(key=lambda f: f["Price (₹)"])
    return flights


def search_hotels(from_location, destination, days):
    rng = random.Random(_seed_for(from_location, destination) + 7)
    hotels = []
    for template in HOTEL_OPTIONS:
        per_day = max(template["Base Price/Day"] + rng.randint(-400, 400), 900)
        hotels.append({
            "Hotel Name": template["Hotel Name"],
            "Rating": f"{template['Stars']:.1f}",
            "Area": template["Area"],
            "Price/Day (₹)": per_day,
            "Total Cost (₹)": per_day * days,
        })
    hotels.sort(key=lambda h: h["Total Cost (₹)"])
    return hotels


def search_attractions(interests):
    results = []
    seen = set()
    for interest in interests:
        for name, icon in ATTRACTION_DB.get(interest.lower(), []):
            if name not in seen:
                seen.add(name)
                results.append({"name": name, "icon": icon, "category": interest})
    if not results:
        results = [
            {"name": "City Walk", "icon": "📍", "category": "general"},
            {"name": "Local Market", "icon": "🛍", "category": "general"},
        ]
    return results

# ---------------- GEOCODING & WEATHER ----------------
POPULAR_DESTINATIONS = {
    "mumbai": (19.0760, 72.8777),
    "delhi": (28.6139, 77.2090),
    "new delhi": (28.6139, 77.2090),
    "bangalore": (12.9716, 77.5946),
    "bengaluru": (12.9716, 77.5946),
    "jaipur": (26.9124, 75.7873),
    "goa": (15.2993, 74.1240),
    "chennai": (13.0827, 80.2707),
    "kolkata": (22.5726, 88.3639),
    "hyderabad": (17.3850, 78.4867),
    "pune": (18.5204, 73.8567),
    "ahmedabad": (23.0225, 72.5714),
    "agra": (27.1767, 78.0081),
    "varanasi": (25.3176, 82.9739),
    "udaipur": (24.5854, 73.7125),
    "manali": (32.2432, 77.1892),
    "shimla": (31.1048, 77.1734),
    "kerala": (10.8505, 76.2711),
    "kochi": (9.9312, 76.2673),
    "paris": (48.8566, 2.3522),
    "london": (51.5074, -0.1278),
    "tokyo": (35.6762, 139.6503),
    "dubai": (25.2048, 55.2708),
    "singapore": (1.3521, 103.8198),
    "new york": (40.7128, -74.0060),
    "rome": (41.9028, 12.4964),
    "bangkok": (13.7563, 100.5018),
    "bali": (-8.4095, 115.1889),
    "amsterdam": (52.3676, 4.9041),
}

WMO_WEATHER_CODES = {
    0: ("Clear sky", "☀️", "Great day for outdoor walks, sightseeing, and photos!"),
    1: ("Mainly clear", "🌤️", "Pleasant weather with mild sunshine."),
    2: ("Partly cloudy", "⛅", "Ideal conditions for walking tours and cafes."),
    3: ("Overcast", "☁️", "Good for museums, heritage sites, and indoor dining."),
    45: ("Foggy", "🌫️", "Low visibility; take care during early morning travel."),
    48: ("Depositing rime fog", "🌫️", "Chilly and misty conditions."),
    51: ("Light drizzle", "🌦️", "Light rain expected; keep an umbrella handy."),
    53: ("Moderate drizzle", "🌦️", "Drizzly weather; light rain gear recommended."),
    55: ("Dense drizzle", "🌧️", "Wet conditions; consider indoor attractions."),
    61: ("Slight rain", "🌧️", "Passersby showers; keep a compact umbrella."),
    63: ("Moderate rain", "🌧️", "Rainy day; good time for covered attractions."),
    65: ("Heavy rain", "⛈️", "Heavy rainfall; stay dry and enjoy cozy local spots."),
    71: ("Slight snowfall", "🌨️", "Light snow; bundle up in warm layers!"),
    73: ("Moderate snowfall", "❄️", "Snowy conditions; warm winter gear needed."),
    75: ("Heavy snowfall", "❄️", "Heavy snow; beautiful scenery, stay warm!"),
    80: ("Rain showers", "🌦️", "Scattered showers likely throughout the day."),
    81: ("Moderate showers", "🌧️", "Periodic rain; plan flexible timings."),
    82: ("Violent showers", "⛈️", "Intense showers; head indoors."),
    95: ("Thunderstorm", "⚡", "Thunderstorms reported; stay in safe sheltered areas."),
}

@st.cache_data(show_spinner=False, ttl=3600)
def get_destination_coords(city_name):
    clean = city_name.strip().lower()
    if clean in POPULAR_DESTINATIONS:
        return POPULAR_DESTINATIONS[clean]
    try:
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(city_name)}&count=1&language=en&format=json"
        req = urllib.request.Request(url, headers={"User-Agent": "VoyagerTravelPlanner/1.0"})
        with urllib.request.urlopen(req, timeout=4) as response:
            data = json.loads(response.read().decode())
            if data.get("results"):
                res = data["results"][0]
                return float(res["latitude"]), float(res["longitude"])
    except Exception:
        pass
    # Deterministic default fallback based on city name hash around India's center
    h = int(hashlib.md5(city_name.encode()).hexdigest(), 16)
    lat = 20.0 + ((h % 1000) / 100.0)
    lon = 73.0 + (((h >> 10) % 1000) / 100.0)
    return lat, lon

@st.cache_data(show_spinner=False, ttl=1800)
def get_weather_forecast(lat, lon):
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat:.4f}&longitude={lon:.4f}"
            "&daily=temperature_2m_max,temperature_2m_min,weathercode,precipitation_probability_max"
            "&current_weather=true&timezone=auto"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "VoyagerTravelPlanner/1.0"})
        with urllib.request.urlopen(req, timeout=4) as response:
            data = json.loads(response.read().decode())
            current = data.get("current_weather", {})
            daily = data.get("daily", {})

            curr_code = current.get("weathercode", 0)
            condition, icon, tip = WMO_WEATHER_CODES.get(curr_code, ("Fair", "🌤️", "Comfortable travel weather."))

            forecast_days = []
            dates = daily.get("time", [])
            max_temps = daily.get("temperature_2m_max", [])
            min_temps = daily.get("temperature_2m_min", [])
            codes = daily.get("weathercode", [])
            rain_probs = daily.get("precipitation_probability_max", [])

            for i in range(min(5, len(dates))):
                w_code = codes[i] if i < len(codes) else 0
                d_cond, d_icon, _ = WMO_WEATHER_CODES.get(w_code, ("Fair", "🌤️", ""))
                d_obj = datetime.strptime(dates[i], "%Y-%m-%d")
                forecast_days.append({
                    "date": d_obj.strftime("%a, %b %d"),
                    "max_temp": round(max_temps[i]) if i < len(max_temps) else "--",
                    "min_temp": round(min_temps[i]) if i < len(min_temps) else "--",
                    "condition": d_cond,
                    "icon": d_icon,
                    "rain_prob": rain_probs[i] if (rain_probs and i < len(rain_probs)) else 0,
                })

            return {
                "available": True,
                "current_temp": round(current.get("temperature", 24)),
                "windspeed": round(current.get("windspeed", 10)),
                "condition": condition,
                "icon": icon,
                "tip": tip,
                "daily": forecast_days,
            }
    except Exception:
        return {
            "available": False,
            "current_temp": 24,
            "windspeed": 8,
            "condition": "Mild & Pleasant",
            "icon": "🌤️",
            "tip": "Comfortable weather expected for your trip.",
            "daily": [],
        }

def generate_map_dataframe(destination, coords, hotel, attractions):
    lat, lon = coords
    points = []

    # 1. Destination Center
    points.append({
        "name": f"{destination} (City Center)",
        "type": "📍 City Hub",
        "details": f"Main hub for {destination}",
        "lat": lat,
        "lon": lon,
        "color": [251, 191, 36, 230],
        "radius": 550,
    })

    # 2. Selected Hotel (offset slightly based on hotel name)
    hotel_hash = int(hashlib.md5(hotel["Hotel Name"].encode()).hexdigest(), 16)
    hotel_lat_off = ((hotel_hash % 100) - 50) * 0.0003
    hotel_lon_off = (((hotel_hash >> 8) % 100) - 50) * 0.0003
    points.append({
        "name": f"🏨 {hotel['Hotel Name']}",
        "type": f"Stay · {hotel.get('Area', 'City Center')}",
        "details": f"⭐ {hotel.get('Rating', '4.2')} · ₹{hotel.get('Price/Day (₹)', 2000):,}/night",
        "lat": lat + hotel_lat_off,
        "lon": lon + hotel_lon_off,
        "color": [168, 85, 247, 240],
        "radius": 480,
    })

    # 3. Attractions distributed around destination
    num_attractions = max(len(attractions), 1)
    for idx, att in enumerate(attractions):
        angle = (2 * math.pi * idx) / num_attractions + 0.35
        dist = 0.015 + ((idx % 3) * 0.008)
        att_lat = lat + math.sin(angle) * dist
        att_lon = lon + math.cos(angle) * dist
        points.append({
            "name": f"{att.get('icon', '📍')} {att['name']}",
            "type": f"Attraction · {att.get('category', 'General').capitalize()}",
            "details": f"Recommended for {att.get('category', 'interests')} lovers",
            "lat": att_lat,
            "lon": att_lon,
            "color": [52, 211, 153, 230],
            "radius": 420,
        })

    return pd.DataFrame(points)

# ---------------- PACKING CHECKLIST ----------------
def generate_packing_list(destination, days, weather, interests):
    current_temp = weather.get("current_temp", 24)
    condition = str(weather.get("condition", "")).lower()
    daily = weather.get("daily", [])

    max_temps = [d.get("max_temp") for d in daily if isinstance(d.get("max_temp"), (int, float))]
    min_temps = [d.get("min_temp") for d in daily if isinstance(d.get("min_temp"), (int, float))]
    max_t = max(max_temps) if max_temps else current_temp
    min_t = min(min_temps) if min_temps else current_temp
    has_rain = (
        any(d.get("rain_prob", 0) > 20 or "rain" in str(d.get("condition", "")).lower() for d in daily)
        or "rain" in condition
        or "drizzle" in condition
    )

    categories = {
        "🪪 Documents & Money": [
            "Government photo ID & booking confirmations",
            "Emergency cash & primary payment cards",
            "Boarding pass / ticket printouts or offline copies",
            "Medical insurance card / emergency contact card",
        ],
        "👕 Clothing & Footwear": [
            f"{max(days, 2)} daily breathable outfits",
            "1 pair durable, broken-in walking shoes",
            "Comfortable sleepwear & undergarments",
            "Light extra layer for transit / air conditioning",
        ],
        "🌤️ Weather Essentials": [],
        "🔌 Tech & Gear": [
            "Smartphone charger & fast charging cable",
            "High-capacity power bank (10,000+ mAh)",
            "Noise-cancelling earbuds or headphones",
        ],
        "🧴 Toiletries & Health": [
            "Travel-size dental kit (brush, paste, floss)",
            "Moisturizer & lip balm",
            "Personal prescription meds & pain reliever",
            "Antiseptic wipes & hand sanitizer",
        ],
        "🎯 Interest-Specific": [],
    }

    # Weather-based logic
    if max_t >= 26 or "clear" in condition or "sun" in condition:
        categories["🌤️ Weather Essentials"].extend([
            "UV protection sunglasses",
            "Broad-spectrum sunscreen (SPF 50+)",
            "Sun hat or cap",
            "Light breathable cotton or linen clothing",
        ])
    if min_t <= 18:
        categories["🌤️ Weather Essentials"].extend([
            "Warm fleece, sweater, or compact jacket",
            "Cozy socks for chilly mornings/evenings",
        ])
    if min_t <= 10:
        categories["🌤️ Weather Essentials"].extend([
            "Thermal innerwear & woolen beanie/scarf",
        ])
    if has_rain:
        categories["🌤️ Weather Essentials"].extend([
            "Compact travel umbrella",
            "Lightweight rain poncho or waterproof jacket",
            "Waterproof pouch for phone & cash",
        ])
    if not categories["🌤️ Weather Essentials"]:
        categories["🌤️ Weather Essentials"].extend([
            "Versatile all-weather light jacket",
            "UV sunglasses & compact umbrella",
        ])

    # Interest-based additions
    norm_interests = [i.lower() for i in interests]
    if "adventure" in norm_interests:
        categories["🎯 Interest-Specific"].extend([
            "Grip-soled hiking/trekking shoes",
            "Lightweight day backpack",
            "Blister bandages & muscle relief spray",
            "Bug spray / insect repellent",
        ])
    if "nature" in norm_interests:
        categories["🎯 Interest-Specific"].extend([
            "Compact binoculars or zoom camera",
            "Reusable insulated water bottle",
            "Eco-friendly insect repellent lotion",
        ])
    if "food" in norm_interests:
        categories["🎯 Interest-Specific"].extend([
            "Digestive tablets & antacids",
            "Pocket pack of wet wipes & sanitizing gel",
            "Reusable food box / silicone bag for street treats",
        ])
    if "history" in norm_interests:
        categories["🎯 Interest-Specific"].extend([
            "Modest clothing for religious & heritage monuments",
            "Slip-on shoes for temple entry/exit ease",
            "Small notebook or travel journal",
        ])

    if not categories["🎯 Interest-Specific"]:
        categories["🎯 Interest-Specific"].extend([
            "Foldable tote bag for market shopping & souvenirs",
            "Compact reusable water bottle",
        ])

    return categories

# ---------------- LANGUAGE & CULTURAL GUIDE ----------------
LANGUAGE_PROFILES = {
    "hindi": {
        "language": "Hindi (हिंदी)",
        "greeting": "Namaste (नमस्ते)",
        "script": "देवनागरी",
        "phrases": [
            {"english": "Hello / Greetings", "local": "नमस्ते", "pronunciation": "Namaste", "category": "General"},
            {"english": "Thank you", "local": "धन्यवाद / शुक्रिया", "pronunciation": "Dhanyavaad / Shukriya", "category": "General"},
            {"english": "Please", "local": "कृपया", "pronunciation": "Kripya", "category": "General"},
            {"english": "How much is this?", "local": "यह कितने का है?", "pronunciation": "Yeh kitne ka hai?", "category": "Shopping"},
            {"english": "Where is the station / market?", "local": "स्टेशन / बाज़ार कहाँ है?", "pronunciation": "Station / Bazaar kahan hai?", "category": "Directions"},
            {"english": "Is this vegetarian?", "local": "क्या यह शाकाहारी है?", "pronunciation": "Kya yeh shakahari hai?", "category": "Dining"},
            {"english": "The bill / check please", "local": "बिल दे दीजिए", "pronunciation": "Bill de dijiye", "category": "Dining"},
            {"english": "Please help me", "local": "कृपया मदद कीजिए", "pronunciation": "Kripya madad kijiye", "category": "Emergency"},
        ],
        "etiquette": [
            "👟 Remove footwear before entering temples, shrines, and local households.",
            "🙏 Greet locals with folded hands and a warm 'Namaste'.",
            "💵 Respectful bargaining is customary in traditional street bazaars; start ~30% below quote.",
            "🍽️ Use your right hand when accepting food, Prasad, or handing payment.",
            "💳 Tipping around 7-10% is customary at sit-down diners and cafes.",
        ],
        "emergency": [
            {"service": "National Emergency Number", "number": "112"},
            {"service": "Police Helpline", "number": "100"},
            {"service": "Medical Ambulance", "number": "108"},
            {"service": "Tourist Helpline (24x7)", "number": "1363"},
        ],
    },
    "marathi": {
        "language": "Marathi (मराठी) & Hindi",
        "greeting": "Namaskar (नमस्कार)",
        "script": "देवनागरी",
        "phrases": [
            {"english": "Hello", "local": "नमस्कार", "pronunciation": "Namaskar", "category": "General"},
            {"english": "Thank you", "local": "धन्यवाद / आभार", "pronunciation": "Dhanyavaad", "category": "General"},
            {"english": "How much is this?", "local": "हे कितीला आहे?", "pronunciation": "He kitila aahe?", "category": "Shopping"},
            {"english": "Where is the station?", "local": "स्थानक कुठे आहे?", "pronunciation": "Sthanak kuthe aahe?", "category": "Directions"},
            {"english": "Very delicious", "local": "खूप छान आहे", "pronunciation": "Khoop chaan aahe", "category": "Dining"},
            {"english": "Please help me", "local": "कृपया मला मदत करा", "pronunciation": "Krupaya madat kara", "category": "Emergency"},
        ],
        "etiquette": [
            "🚆 Suburban local trains are Mumbai's lifeline; keep backpack in front during peak hours.",
            "👟 Remove footwear before entering temples and prayer rooms.",
            "🚕 City black-and-yellow taxis and auto-rickshaws strictly use electronic meters.",
            "💵 5-10% tipping is customary at sit-down eateries.",
        ],
        "emergency": [
            {"service": "National Emergency", "number": "112"},
            {"service": "Police Helpline", "number": "100"},
            {"service": "Medical Ambulance", "number": "108"},
            {"service": "Tourist Helpline", "number": "1363"},
        ],
    },
    "kannada": {
        "language": "Kannada (ಕನ್ನಡ) & English",
        "greeting": "Namaskara (ನಮಸ್ಕಾರ)",
        "script": "ಕನ್ನಡ ಲಿಪಿ",
        "phrases": [
            {"english": "Hello", "local": "ನಮಸ್ಕಾರ", "pronunciation": "Namaskara", "category": "General"},
            {"english": "Thank you", "local": "ಧನ್ಯವಾದಗಳು", "pronunciation": "Dhanyavaadagalu", "category": "General"},
            {"english": "How much is this?", "local": "ಇದು ಎಷ್ಟು?", "pronunciation": "Idu eshtu?", "category": "Shopping"},
            {"english": "Where is this place?", "local": "ಈ ಜಾಗ ಎಲ್ಲಿದೆ?", "pronunciation": "Ee jaaga ellide?", "category": "Directions"},
            {"english": "Food is very tasty", "local": "ತಿಂಡಿ ತುಂಬಾ ಚೆನ್ನಾಗಿದೆ", "pronunciation": "Tindi tumba chennagide", "category": "Dining"},
            {"english": "Please help", "local": "ದಯವಿಟ್ಟು ಸಹಾಯ ಮಾಡಿ", "pronunciation": "Dayavittu sahaya maadi", "category": "Emergency"},
        ],
        "etiquette": [
            "☕ Filter coffee and darshini breakfast counters are iconic; order and stand by the counters.",
            "🗣️ English and Hindi are widely understood alongside Kannada across commercial areas.",
            "👟 Leave shoes outside places of worship.",
            "🚕 Ride-hailing apps (Uber, Ola, Namma Yatri) are most convenient for city commute.",
        ],
        "emergency": [
            {"service": "National Emergency", "number": "112"},
            {"service": "Police", "number": "100"},
            {"service": "Ambulance", "number": "108"},
            {"service": "Tourist Helpline", "number": "1363"},
        ],
    },
    "french": {
        "language": "French (Français)",
        "greeting": "Bonjour",
        "script": "Latin",
        "phrases": [
            {"english": "Hello / Good day", "local": "Bonjour", "pronunciation": "Bohn-zhoor", "category": "General"},
            {"english": "Thank you very much", "local": "Merci beaucoup", "pronunciation": "Mair-see boh-koo", "category": "General"},
            {"english": "Please", "local": "S'il vous plaît", "pronunciation": "Seel voo play", "category": "General"},
            {"english": "How much is this?", "local": "Combien ça coûte ?", "pronunciation": "Kom-byen sah koot?", "category": "Shopping"},
            {"english": "Where is the metro?", "local": "Où est le métro ?", "pronunciation": "Oo ay luh may-tro?", "category": "Directions"},
            {"english": "The bill, please", "local": "L'addition, s'il vous plaît", "pronunciation": "Lah-dee-syon seel voo play", "category": "Dining"},
            {"english": "Help!", "local": "Au secours !", "pronunciation": "Oh seh-koor!", "category": "Emergency"},
        ],
        "etiquette": [
            "🥐 Always greet shopkeepers and waitstaff with 'Bonjour' upon entering.",
            "🍷 A 15% service fee is already included in restaurant checks by French law.",
            "🚇 Stand on the right side of escalators in the Metro so commuters can walk on the left.",
            "👗 Smart casual attire is appreciated when dining in evening bistros.",
        ],
        "emergency": [
            {"service": "European Emergency", "number": "112"},
            {"service": "Medical SAMU", "number": "15"},
            {"service": "Police", "number": "17"},
            {"service": "Fire Rescue", "number": "18"},
        ],
    },
    "japanese": {
        "language": "Japanese (日本語)",
        "greeting": "Konnichiwa (こんにちは)",
        "script": "漢字 / かな",
        "phrases": [
            {"english": "Hello", "local": "こんにちは", "pronunciation": "Konnichiwa", "category": "General"},
            {"english": "Thank you very much", "local": "ありがとうございます", "pronunciation": "Arigatō gozaimasu", "category": "General"},
            {"english": "Excuse me / Sorry", "local": "すみません", "pronunciation": "Sumimasen", "category": "General"},
            {"english": "How much is this?", "local": "これはいくらですか？", "pronunciation": "Kore wa ikura desu ka?", "category": "Shopping"},
            {"english": "Where is the station?", "local": "駅はどこですか？", "pronunciation": "Eki wa doko desu ka?", "category": "Directions"},
            {"english": "Delicious!", "local": "おいしいです！", "pronunciation": "Oishii desu!", "category": "Dining"},
            {"english": "Check please", "local": "お会計をお願いします", "pronunciation": "O-kaikei o onegaishimasu", "category": "Dining"},
            {"english": "Please help me", "local": "助けてください", "pronunciation": "Tasukete kudasai", "category": "Emergency"},
        ],
        "etiquette": [
            "🚫 Tipping is not customary in Japan and can cause confusion or embarrassment.",
            "👟 Always remove your shoes when stepping onto tatami mats, shrines, and ryokans.",
            "🤫 Avoid loud conversations or phone calls on bullet trains and public transport.",
            "🍜 Slurping ramen noodles is welcomed and viewed as a compliment to the chef!",
        ],
        "emergency": [
            {"service": "Police", "number": "110"},
            {"service": "Ambulance & Fire", "number": "119"},
            {"service": "Japan Tourist Hotline", "number": "050-3816-2720"},
        ],
    },
    "general": {
        "language": "Global Travel English & Local Courtesy",
        "greeting": "Hello / Good Day",
        "script": "International",
        "phrases": [
            {"english": "Hello / Good day", "local": "Hello / Good Day", "pronunciation": "Hel-lo", "category": "General"},
            {"english": "Thank you very much", "local": "Thank you very much", "pronunciation": "Thank you", "category": "General"},
            {"english": "Could you please help me?", "local": "Could you please help me?", "pronunciation": "Help please", "category": "General"},
            {"english": "How much does this cost?", "local": "How much is this?", "pronunciation": "Price check", "category": "Shopping"},
            {"english": "Where is the main station?", "local": "Where is the station?", "pronunciation": "Station directions", "category": "Directions"},
            {"english": "Check / Bill please", "local": "The bill, please", "pronunciation": "Bill please", "category": "Dining"},
            {"english": "Emergency / Police", "local": "I need urgent assistance", "pronunciation": "Help", "category": "Emergency"},
        ],
        "etiquette": [
            "🧭 Keep offline maps downloaded on your smartphone for low connectivity spots.",
            "💳 Carry a mix of local cash and a foreign transaction-free card.",
            "🤝 Respect local dress codes at cultural landmarks and places of worship.",
            "📸 Always ask before photographing individuals, vendors, or sacred rituals.",
        ],
        "emergency": [
            {"service": "International Emergency", "number": "112 / 911"},
            {"service": "Local Police & Assistance", "number": "Inquire at Hotel Desk"},
        ],
    },
}

def get_destination_language_guide(destination):
    dest = destination.strip().lower()
    if any(k in dest for k in ["mumbai", "pune", "nagpur", "nashik"]):
        return LANGUAGE_PROFILES["marathi"]
    if any(k in dest for k in ["bangalore", "bengaluru", "mysore", "mysuru", "hampi", "coorg"]):
        return LANGUAGE_PROFILES["kannada"]
    if any(k in dest for k in ["paris", "nice", "lyon", "marseille", "france"]):
        return LANGUAGE_PROFILES["french"]
    if any(k in dest for k in ["tokyo", "kyoto", "osaka", "japan"]):
        return LANGUAGE_PROFILES["japanese"]
    if any(k in dest for k in ["jaipur", "delhi", "agra", "varanasi", "udaipur", "goa", "india", "lucknow", "jodhpur", "manali", "shimla"]):
        return LANGUAGE_PROFILES["hindi"]
    return LANGUAGE_PROFILES["general"]

# ---------------- AI ITINERARY ----------------
def generate_itinerary(from_location, destination, start_date, end_date, interests):
    if not client:
        return f"""**Day 1: Arrival in {destination}**
Settle into your hotel and explore the nearby neighborhood. Take a leisurely walk to get oriented with the area.

**Day 2: Exploring {destination}**
Visit the top attractions based on your interests: {', '.join(interests)}. Start with the most popular spot in the morning when it's less crowded.

**Day 3: Hidden Gems & Departure**
Discover local favorites — cafés, markets, and viewpoints. Pack up and head back to {from_location} with wonderful memories."""

    try:
        prompt = f"""Create a detailed, engaging day-by-day travel itinerary. Format it with markdown headers for each day.

From: {from_location}
Destination: {destination}
Dates: {start_date} to {end_date}
Interests: {', '.join(interests)}

Make it conversational and inspiring. Include specific suggestions for each day."""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an expert travel planner. Create detailed, engaging itineraries with markdown formatting. Use headers for each day and include practical tips."},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content

    except Exception:
        return "⚠️ AI service unavailable. Showing basic itinerary."

# ---------------- COST ----------------
def calculate_total_cost(flight_cost, hotel_cost, days):
    food_cost = days * 800
    transport_cost = days * 500
    return flight_cost + hotel_cost + food_cost + transport_cost

# ---------------- PDF ----------------
def _strip_markdown(text):
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"\1", text)
    return text.strip()


def create_pdf(from_location, destination, total_cost, itinerary, flight, hotel, days):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()
    content = []

    content.append(Paragraph("Voyager — Travel Itinerary", styles["Title"]))
    content.append(Spacer(1, 10))
    content.append(Paragraph(f"<b>Route:</b> {escape(from_location)} → {escape(destination)}", styles["Normal"]))
    content.append(Paragraph(f"<b>Duration:</b> {days} days", styles["Normal"]))
    content.append(Paragraph(f"<b>Estimated Cost:</b> ₹{total_cost:,}", styles["Normal"]))
    content.append(Spacer(1, 10))
    content.append(Paragraph("<b>Flight:</b> {} — ₹{}".format(escape(flight['Airline']), flight['Price (₹)']), styles["Normal"]))
    content.append(Paragraph("<b>Hotel:</b> {} — ₹{:,}".format(escape(hotel['Hotel Name']), hotel['Total Cost (₹)']), styles["Normal"]))
    content.append(Spacer(1, 15))
    content.append(Paragraph("<b>Itinerary</b>", styles["Heading2"]))
    content.append(Spacer(1, 5))

    for line in itinerary.split("\n"):
        stripped = line.strip()
        if not stripped:
            content.append(Spacer(1, 6))
            continue
        if stripped.startswith("#"):
            heading = _strip_markdown(stripped.lstrip("#").strip())
            content.append(Spacer(1, 8))
            content.append(Paragraph(escape(heading), styles["Heading2"]))
        elif re.match(r"^[-*]\s+", stripped):
            bullet = _strip_markdown(re.sub(r"^[-*]\s+", "", stripped))
            content.append(Paragraph(f"• {escape(bullet)}", styles["Normal"]))
        else:
            content.append(Paragraph(escape(_strip_markdown(stripped)), styles["Normal"]))

    doc.build(content)
    buffer.seek(0)
    return buffer

# ---------------- DESIGN SYSTEM ----------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --bg-primary: #0c0f14;
    --bg-secondary: #131720;
    --bg-tertiary: #1a1f2b;
    --bg-card: #161b26;
    --bg-hover: #1e2433;
    --accent: #6c63ff;
    --accent-soft: rgba(108, 99, 255, 0.12);
    --accent-glow: rgba(108, 99, 255, 0.25);
    --text-primary: #e8eaf0;
    --text-secondary: #8b90a0;
    --text-muted: #555b6e;
    --border: #1f2537;
    --border-subtle: #1a1f2a;
    --success: #34d399;
    --warning: #fbbf24;
    --error: #f87171;
}

* { box-sizing: border-box; }

section[data-testid="stSidebar"] {
    background: var(--bg-secondary) !important;
    border-right: 1px solid var(--border) !important;
}

section[data-testid="stSidebar"] > div {
    padding-top: 2rem !important;
}

section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: var(--text-secondary) !important;
}

/* Global typography */
html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif !important;
    color: var(--text-primary) !important;
}

.stApp {
    background: var(--bg-primary) !important;
}

/* Header */
.main .block-container {
    padding-top: 2rem !important;
    max-width: 1200px !important;
}

/* Metric cards */
[data-testid="stMetric"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    padding: 20px 24px !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}

[data-testid="stMetric"]:hover {
    border-color: var(--accent) !important;
    box-shadow: 0 0 20px var(--accent-soft) !important;
}

[data-testid="stMetric"] label {
    color: var(--text-secondary) !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
}

[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: var(--text-primary) !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 1.3rem !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px !important;
    background: var(--bg-secondary) !important;
    border-radius: 10px !important;
    padding: 4px !important;
    border: 1px solid var(--border) !important;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important;
    padding: 10px 20px !important;
    color: var(--text-secondary) !important;
    font-weight: 500 !important;
    font-size: 0.9rem !important;
    background: transparent !important;
    border: none !important;
    transition: all 0.2s ease !important;
}

.stTabs [aria-selected="true"] {
    background: var(--bg-tertiary) !important;
    color: var(--text-primary) !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.3) !important;
}

.stTabs [data-baseweb="tab"]:hover:not([aria-selected="true"]) {
    color: var(--text-primary) !important;
    background: var(--bg-hover) !important;
}

/* Buttons */
.stButton > button {
    background: var(--accent) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    padding: 10px 28px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.95rem !important;
    transition: all 0.2s ease !important;
    letter-spacing: 0.01em !important;
}

.stButton > button:hover {
    background: #5b52e0 !important;
    box-shadow: 0 4px 20px var(--accent-glow) !important;
    transform: translateY(-1px) !important;
}

.stButton > button:active {
    transform: translateY(0px) !important;
}

/* Download button */
.stDownloadButton > button {
    background: transparent !important;
    color: var(--accent) !important;
    border: 1px solid var(--accent) !important;
    border-radius: 10px !important;
    font-weight: 500 !important;
    transition: all 0.2s ease !important;
}

.stDownloadButton > button:hover {
    background: var(--accent-soft) !important;
    box-shadow: 0 0 16px var(--accent-soft) !important;
}

/* Text inputs */
.stTextInput > div > div > input,
.stNumberInput > div > div > input {
    background: var(--bg-tertiary) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    color: var(--text-primary) !important;
    padding: 12px 16px !important;
    font-family: 'DM Sans', sans-serif !important;
    transition: border-color 0.2s ease !important;
}

.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accent-soft) !important;
}

.stDateInput > div > div > input {
    background: var(--bg-tertiary) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    color: var(--text-primary) !important;
}

/* Labels */
.stTextInput label,
.stDateInput label,
.stNumberInput label,
.stMultiSelect label {
    color: var(--text-secondary) !important;
    font-weight: 500 !important;
    font-size: 0.85rem !important;
    letter-spacing: 0.02em !important;
}

/* Select / Multiselect */
[data-baseweb="select"] {
    background: var(--bg-tertiary) !important;
    border-color: var(--border) !important;
    border-radius: 10px !important;
}

[data-baseweb="tag"] {
    background: var(--accent-soft) !important;
    color: var(--accent) !important;
    border-radius: 6px !important;
}

/* Info/Warning/Error boxes */
.stAlert {
    background: var(--bg-card) !important;
    border-radius: 10px !important;
    border: 1px solid var(--border) !important;
    color: var(--text-secondary) !important;
}

/* Dividers */
.stDivider {
    border-color: var(--border) !important;
}

/* Chat */
.stChatMessage {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
}

/* Sidebar header */
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: var(--text-primary) !important;
    font-weight: 600 !important;
}

/* Custom card component */
.voyager-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 28px;
    transition: all 0.25s ease;
}

.voyager-card:hover {
    border-color: var(--accent);
    box-shadow: 0 4px 24px rgba(108, 99, 255, 0.08);
}

.voyager-section-title {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    margin-bottom: 8px;
}

.voyager-accent-text {
    color: var(--accent);
    font-weight: 600;
}

.voyager-price {
    font-family: 'JetBrains Mono', monospace;
    font-weight: 500;
    color: var(--text-primary);
    font-size: 1.1rem;
}

.voyager-tag {
    display: inline-block;
    padding: 4px 12px;
    background: var(--accent-soft);
    color: var(--accent);
    border-radius: 6px;
    font-size: 0.8rem;
    font-weight: 500;
    margin: 2px 4px 2px 0;
}

.voyager-attraction-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 18px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    margin-bottom: 8px;
    transition: all 0.2s ease;
}

.voyager-attraction-item:hover {
    border-color: var(--accent);
    background: var(--bg-hover);
}

.voyager-attraction-icon {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    background: var(--accent-soft);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1rem;
    flex-shrink: 0;
}

.voyager-hero-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 16px;
    background: var(--accent-soft);
    border: 1px solid rgba(108, 99, 255, 0.2);
    border-radius: 100px;
    font-size: 0.82rem;
    font-weight: 500;
    color: var(--accent);
    margin-bottom: 20px;
}

.voyager-cost-bar {
    height: 4px;
    background: var(--bg-tertiary);
    border-radius: 4px;
    overflow: hidden;
    margin-top: 8px;
}

.voyager-cost-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--accent), #a78bfa);
    border-radius: 4px;
    transition: width 0.6s ease;
}

.voyager-empty-state {
    text-align: center;
    padding: 60px 40px;
    background: var(--bg-card);
    border: 1px dashed var(--border);
    border-radius: 16px;
}

.voyager-empty-icon {
    font-size: 3rem;
    margin-bottom: 16px;
    opacity: 0.6;
}

/* Weather & Map Components */
.voyager-weather-hero {
    background: linear-gradient(135deg, var(--bg-card) 0%, var(--bg-tertiary) 100%);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 20px 24px;
    margin-bottom: 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 16px;
}

.voyager-weather-container {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 12px;
    margin-top: 14px;
    margin-bottom: 20px;
}

.voyager-weather-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 12px;
    text-align: center;
    transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.voyager-weather-card:hover {
    transform: translateY(-2px);
    border-color: var(--accent);
    box-shadow: 0 4px 16px var(--accent-soft);
}

.voyager-weather-date {
    font-size: 0.78rem;
    color: var(--text-muted);
    margin-bottom: 4px;
    font-weight: 500;
}

.voyager-weather-icon {
    font-size: 1.8rem;
    margin: 4px 0;
}

.voyager-weather-temp {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.05rem;
    font-weight: 600;
    color: var(--text-primary);
}

.voyager-weather-condition {
    font-size: 0.75rem;
    color: var(--text-secondary);
    margin-top: 4px;
}

.voyager-map-legend {
    display: flex;
    gap: 20px;
    flex-wrap: wrap;
    align-items: center;
    padding: 10px 18px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    margin-bottom: 14px;
    font-size: 0.82rem;
    color: var(--text-secondary);
}

.voyager-legend-item {
    display: flex;
    align-items: center;
    gap: 8px;
}

.voyager-legend-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    display: inline-block;
}

/* Packing Checklist Components */
.voyager-checklist-progress {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px 22px;
    margin-bottom: 22px;
}

.voyager-category-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 16px;
    transition: border-color 0.2s ease;
}

.voyager-category-card:hover {
    border-color: rgba(108, 99, 255, 0.4);
}

.voyager-category-title {
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* Language & Etiquette Guide */
.voyager-phrase-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 12px;
    margin-top: 12px;
    margin-bottom: 20px;
}

.voyager-phrase-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 14px 16px;
    transition: transform 0.2s ease, border-color 0.2s ease;
}

.voyager-phrase-card:hover {
    transform: translateY(-2px);
    border-color: var(--accent);
}

.voyager-phrase-english {
    font-size: 0.82rem;
    color: var(--text-muted);
    margin-bottom: 4px;
}

.voyager-phrase-local {
    font-size: 1.15rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 4px;
}

.voyager-phrase-phonetic {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.85rem;
    color: var(--accent);
    font-style: italic;
}

.voyager-etiquette-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 16px;
}

.voyager-emergency-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 14px;
    background: var(--bg-tertiary);
    border-radius: 8px;
    margin-bottom: 8px;
}

/* Scrollbar */
::-webkit-scrollbar {
    width: 6px;
}

::-webkit-scrollbar-track {
    background: var(--bg-primary);
}

::-webkit-scrollbar-thumb {
    background: var(--border);
    border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
    background: var(--text-muted);
}
</style>
""", unsafe_allow_html=True)

# ---------------- TITLE ----------------
st.markdown("""
<div class="voyager-hero-badge">✦ Voyager Travel</div>
""", unsafe_allow_html=True)

st.markdown("""
<h1 style="font-size: 2.4rem; font-weight: 700; margin-top: -8px; margin-bottom: 4px; letter-spacing: -0.02em;">
    Plan your next trip
</h1>
<p style="color: var(--text-secondary); font-size: 1.05rem; margin-bottom: 32px;">
    Smart itineraries powered by AI. Enter your details and let the journey begin.
</p>
""", unsafe_allow_html=True)

memory = load_memory()

if memory:
    dest = memory.get('last_destination', 'somewhere')
    st.markdown(f"""
    <div style="
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-left: 3px solid var(--accent);
        border-radius: 10px;
        padding: 14px 20px;
        margin-bottom: 28px;
        display: flex;
        align-items: center;
        gap: 12px;
    ">
        <span style="font-size: 1.2rem;">📍</span>
        <div>
            <span style="color: var(--text-secondary); font-size: 0.85rem;">Last trip planned</span><br>
            <span style="color: var(--text-primary); font-weight: 500;">{h(memory.get('last_from', '—'))} → {h(dest)}</span>
            <span style="color: var(--text-muted); font-size: 0.8rem; margin-left: 8px;">
                {h(' · '.join(memory.get('last_interests', [])))}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.markdown("""
    <div style="margin-bottom: 24px;">
        <h2 style="font-size: 1.15rem; font-weight: 600; margin-bottom: 2px;">Plan Trip</h2>
        <p style="color: var(--text-muted); font-size: 0.82rem; margin: 0;">Fill in your travel details</p>
    </div>
    """, unsafe_allow_html=True)
    if not client:
        st.warning("GROQ_API_KEY not set. AI chatbot will use fallback responses.", icon="⚠️")

    from_location = clean_location(st.text_input("From", placeholder="e.g. Mumbai"))
    destination = clean_location(st.text_input("Destination", placeholder="e.g. Jaipur"))

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start")
    with col2:
        end_date = st.date_input("End")

    budget = st.number_input("Budget (₹)", min_value=1000, step=500, value=15000)

    interests = st.multiselect(
        "Interests",
        ["nature", "food", "history", "adventure"],
        placeholder="Select interests"
    )

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    submit = st.button("Plan Trip", use_container_width=True)

# ---------------- OUTPUT ----------------
if submit:
    if not from_location or not destination:
        st.session_state.pop("results", None)
        st.session_state.chat_destination = ""
        st.error("Please enter both locations to continue.")
    elif start_date > end_date:
        st.session_state.pop("results", None)
        st.session_state.chat_destination = ""
        st.error("End date must be after start date.")
    else:
        with st.spinner("Planning your trip..."):
            days = (end_date - start_date).days + 1
            coords = get_destination_coords(destination)
            weather = get_weather_forecast(coords[0], coords[1])
            st.session_state.results = {
                "from": from_location,
                "destination": destination,
                "days": days,
                "interests": interests,
                "budget": budget,
                "coords": coords,
                "weather": weather,
                "flights": search_flights(from_location, destination),
                "hotels": search_hotels(from_location, destination, days),
                "attractions": search_attractions(interests),
                "itinerary": generate_itinerary(
                    from_location, destination, str(start_date), str(end_date), interests
                ),
            }
        save_memory(from_location, destination, interests,
                    f"{start_date} — {end_date}", budget)

# ---------------- RESULTS ----------------
results = st.session_state.get("results")

if results:
    from_location = results["from"]
    destination = results["destination"]
    days = results["days"]
    budget = results["budget"]
    attractions = results["attractions"]
    itinerary = results["itinerary"]
    flights = results["flights"]
    hotels = results["hotels"]
    coords = results.get("coords") or get_destination_coords(destination)
    weather = results.get("weather") or get_weather_forecast(coords[0], coords[1])

    # Flight & hotel selection
    st.markdown("<div class='voyager-section-title'>Choose your flight &amp; stay</div>", unsafe_allow_html=True)
    _sc1, _sc2 = st.columns(2)
    with _sc1:
        flight_idx = st.selectbox(
            "✈ Flight",
            options=range(len(flights)),
            format_func=lambda i: f"{flights[i]['Airline']} · {flights[i]['Duration']} · {flights[i]['Stops']} · ₹{flights[i]['Price (₹)']:,}",
        )
    with _sc2:
        hotel_idx = st.selectbox(
            "🏨 Hotel",
            options=range(len(hotels)),
            format_func=lambda i: f"{hotels[i]['Hotel Name']} · ⭐{hotels[i]['Rating']} · ₹{hotels[i]['Price/Day (₹)']:,}/night",
        )
    flight = flights[flight_idx]
    hotel = hotels[hotel_idx]
    total_cost = calculate_total_cost(flight["Price (₹)"], hotel["Total Cost (₹)"], days)

    # Trip summary header
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, var(--bg-card) 0%, var(--bg-tertiary) 100%);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 28px 32px;
        margin-bottom: 24px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 16px;
    ">
        <div>
            <div style="color: var(--text-muted); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px;">Trip Route</div>
            <div style="font-size: 1.5rem; font-weight: 700; letter-spacing: -0.01em;">
                {h(from_location)}
                <span style="color: var(--accent); margin: 0 10px;">→</span>
                {h(destination)}
            </div>
        </div>
        <div style="display: flex; gap: 24px; align-items: center;">
            <div style="text-align: center;">
                <div style="color: var(--text-muted); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em;">Duration</div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 1.1rem; font-weight: 600;">{days}d</div>
            </div>
            <div style="width: 1px; height: 32px; background: var(--border);"></div>
            <div style="text-align: center;">
                <div style="color: var(--text-muted); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em;">Live Climate</div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 1.1rem; font-weight: 600; color: var(--accent);">
                    {weather.get('icon', '🌤️')} {weather.get('current_temp', 24)}°C
                </div>
            </div>
            <div style="width: 1px; height: 32px; background: var(--border);"></div>
            <div style="text-align: center;">
                <div style="color: var(--text-muted); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em;">Budget</div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 1.1rem; font-weight: 600; color: {'var(--success)' if total_cost <= budget else 'var(--error)'};">
                    ₹{total_cost:,}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Budget progress
    if budget > 0:
        pct = min((total_cost / budget) * 100, 100)
        color = "var(--success)" if pct <= 80 else "var(--warning)" if pct <= 100 else "var(--error)"
        st.markdown(f"""
        <div style="margin-top: -12px; margin-bottom: 24px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                <span style="color: var(--text-muted); font-size: 0.78rem;">Budget usage</span>
                <span style="color: {color}; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; font-weight: 500;">{pct:.0f}%</span>
            </div>
            <div class="voyager-cost-bar">
                <div class="voyager-cost-fill" style="width: {pct}%; background: {color};"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Tabs
    tab1, tab_map, tab_weather, tab_packing, tab_phrases, tab2, tab3 = st.tabs([
        "Overview",
        "🗺️ Interactive Map",
        "🌤️ Live Weather",
        "🧳 Smart Packing",
        "🗣️ Local Phrases",
        "📍 Attractions",
        "🗓️ Itinerary"
    ])

    with tab1:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("✈ Flight", f"{flight['Airline']}", f"₹{flight['Price (₹)']:,}")
            st.markdown(f"""
            <div style="display: flex; gap: 8px; margin-top: -8px;">
                <span class="voyager-tag">{flight.get('Duration', '2h 15m')}</span>
                <span class="voyager-tag">{flight.get('Stops', 'Non-stop')}</span>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.metric("🏨 Hotel", hotel['Hotel Name'], f"₹{hotel['Total Cost (₹)']:,} total")
            st.markdown(f"""
            <div style="display: flex; gap: 8px; margin-top: -8px;">
                <span class="voyager-tag">⭐ {hotel.get('Rating', '4.2')}</span>
                <span class="voyager-tag">₹{hotel['Price/Day (₹)']:,}/night</span>
                <span class="voyager-tag">📍 {hotel.get('Area', 'Central')}</span>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            st.metric("🌤️ Climate", f"{weather.get('icon', '🌤️')} {weather.get('current_temp', 24)}°C", f"{weather.get('condition', 'Mild')}")
            st.markdown(f"""
            <div style="display: flex; gap: 8px; margin-top: -8px;">
                <span class="voyager-tag">💨 {weather.get('windspeed', 10)} km/h</span>
                <span class="voyager-tag">📍 {h(destination)}</span>
            </div>
            """, unsafe_allow_html=True)
        with c4:
            st.metric("💰 Total Cost", f"₹{total_cost:,}", f"{days} days")
            st.markdown(f"""
            <div style="display: flex; gap: 8px; margin-top: -8px;">
                <span class="voyager-tag">Food ₹{days * 800:,}</span>
                <span class="voyager-tag">Transport ₹{days * 500:,}</span>
            </div>
            """, unsafe_allow_html=True)

    with tab_map:
        st.markdown(f"""
        <div style="margin-bottom: 12px;">
            <h3 style="font-size: 1.1rem; font-weight: 600; margin-bottom: 4px;">Interactive Destination Map</h3>
            <p style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 14px;">
                Explore {h(destination)}: hotel stay, attractions, and key hubs plotted in 3D dark mode
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="voyager-map-legend">
            <span class="voyager-legend-item">
                <span class="voyager-legend-dot" style="background: #fbbf24;"></span>
                <span>Destination Center</span>
            </span>
            <span class="voyager-legend-item">
                <span class="voyager-legend-dot" style="background: #a855f7;"></span>
                <span>Selected Hotel</span>
            </span>
            <span class="voyager-legend-item">
                <span class="voyager-legend-dot" style="background: #34d399;"></span>
                <span>Recommended Attractions</span>
            </span>
        </div>
        """, unsafe_allow_html=True)

        map_df = generate_map_dataframe(destination, coords, hotel, attractions)

        scatterplot_layer = pdk.Layer(
            "ScatterplotLayer",
            data=map_df,
            get_position="[lon, lat]",
            get_color="color",
            get_radius="radius",
            pickable=True,
            auto_highlight=True,
            radius_min_pixels=6,
            radius_max_pixels=25,
        )

        text_layer = pdk.Layer(
            "TextLayer",
            data=map_df,
            get_position="[lon, lat]",
            get_text="name",
            get_size=12,
            get_color=[232, 234, 240, 220],
            get_alignment_baseline="'bottom'",
            get_pixel_offset=[0, -10],
            font_family="'DM Sans', sans-serif",
        )

        view_state = pdk.ViewState(
            latitude=coords[0],
            longitude=coords[1],
            zoom=12.2,
            pitch=25,
        )

        st.pydeck_chart(
            pdk.Deck(
                layers=[scatterplot_layer, text_layer],
                initial_view_state=view_state,
                tooltip={
                    "html": "<div style='font-family: sans-serif; font-size: 13px; line-height: 1.4;'>"
                            "<b style='color: #6c63ff; font-size: 14px;'>{name}</b><br/>"
                            "<span style='color: #8b90a0;'>{type}</span><br/>"
                            "<span style='color: #e8eaf0;'>{details}</span>"
                            "</div>",
                    "style": {
                        "backgroundColor": "#161b26",
                        "color": "#e8eaf0",
                        "border": "1px solid #1f2537",
                        "borderRadius": "8px",
                        "padding": "10px 14px",
                        "boxShadow": "0 8px 24px rgba(0,0,0,0.5)"
                    }
                },
                map_style="dark",
            )
        )

        st.markdown(f"""
        <div style="margin-top: 10px; display: flex; justify-content: flex-end;">
            <span class="voyager-tag">📍 Lat: {coords[0]:.4f}, Lon: {coords[1]:.4f}</span>
        </div>
        """, unsafe_allow_html=True)

    with tab_weather:
        st.markdown(f"""
        <div style="margin-bottom: 14px;">
            <h3 style="font-size: 1.1rem; font-weight: 600; margin-bottom: 4px;">Weather Forecast for {h(destination)}</h3>
            <p style="color: var(--text-muted); font-size: 0.85rem;">Live conditions &amp; 5-day outlook</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="voyager-weather-hero">
            <div style="display: flex; align-items: center; gap: 20px;">
                <span style="font-size: 3.2rem;">{weather.get('icon', '🌤️')}</span>
                <div>
                    <div style="color: var(--text-muted); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em;">Current Conditions</div>
                    <div style="font-size: 2rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; color: var(--text-primary); margin: 2px 0;">
                        {weather.get('current_temp', 24)}°C
                    </div>
                    <div style="color: var(--text-secondary); font-size: 0.95rem;">{weather.get('condition', 'Mild & Pleasant')}</div>
                </div>
            </div>
            <div style="display: flex; flex-direction: column; gap: 8px;">
                <div style="display: flex; gap: 16px;">
                    <div>
                        <span style="color: var(--text-muted); font-size: 0.75rem; text-transform: uppercase;">Wind Speed</span><br>
                        <span style="font-weight: 600; font-family: 'JetBrains Mono', monospace;">{weather.get('windspeed', 10)} km/h</span>
                    </div>
                    <div>
                        <span style="color: var(--text-muted); font-size: 0.75rem; text-transform: uppercase;">Status</span><br>
                        <span style="color: var(--success); font-weight: 600;">Active</span>
                    </div>
                </div>
                <div style="font-size: 0.85rem; color: var(--accent); background: var(--accent-soft); padding: 6px 12px; border-radius: 8px;">
                    💡 {weather.get('tip', 'Enjoy your journey!')}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        daily = weather.get("daily", [])
        if daily:
            st.markdown("<div style='font-size: 0.88rem; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px;'>5-Day Outlook</div>", unsafe_allow_html=True)
            w_cols = st.columns(len(daily))
            for idx, day_info in enumerate(daily):
                with w_cols[idx]:
                    st.markdown(f"""
                    <div class="voyager-weather-card">
                        <div class="voyager-weather-date">{day_info['date']}</div>
                        <div class="voyager-weather-icon">{day_info['icon']}</div>
                        <div class="voyager-weather-temp">{day_info['max_temp']}° / <span style="color: var(--text-muted); font-size: 0.88rem;">{day_info['min_temp']}°</span></div>
                        <div class="voyager-weather-condition">{day_info['condition']}</div>
                    </div>
                    """, unsafe_allow_html=True)

    with tab_packing:
        st.markdown(f"""
        <div style="margin-bottom: 14px;">
            <h3 style="font-size: 1.1rem; font-weight: 600; margin-bottom: 4px;">Smart Packing Checklist</h3>
            <p style="color: var(--text-muted); font-size: 0.85rem;">Customized for {h(destination)} ({days} days · {weather.get('current_temp', 24)}°C · {weather.get('condition', 'Mild')})</p>
        </div>
        """, unsafe_allow_html=True)

        packing_categories = generate_packing_list(destination, days, weather, interests)

        # Build list of all item keys for persistent tracking
        all_item_keys = []
        for cat, items in packing_categories.items():
            for itm in items:
                all_item_keys.append(f"pack_{destination}_{cat}_{itm}")

        total_items = max(len(all_item_keys), 1)
        packed_count = sum(1 for k in all_item_keys if st.session_state.get(k, False))
        pct_packed = int((packed_count / total_items) * 100)

        p_col1, p_col2 = st.columns([3, 1])
        with p_col1:
            st.markdown(f"""
            <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                <span style="color: var(--text-secondary); font-size: 0.85rem; font-weight: 500;">
                    Packed {packed_count} of {total_items} essentials
                </span>
                <span style="color: {'var(--success)' if pct_packed == 100 else 'var(--accent)'}; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; font-weight: 600;">
                    {pct_packed}% Complete
                </span>
            </div>
            <div class="voyager-cost-bar" style="height: 6px; margin-bottom: 18px;">
                <div class="voyager-cost-fill" style="width: {pct_packed}%; background: {'var(--success)' if pct_packed == 100 else 'var(--accent)'};"></div>
            </div>
            """, unsafe_allow_html=True)

        with p_col2:
            if st.button("Reset Checklist", use_container_width=True):
                for k in all_item_keys:
                    st.session_state[k] = False
                st.rerun()

        # Render categories in clean 2-column cards
        cat_names = list(packing_categories.keys())
        left_col, right_col = st.columns(2)
        for idx, cat in enumerate(cat_names):
            target_col = left_col if idx % 2 == 0 else right_col
            items = packing_categories[cat]
            if items:
                with target_col:
                    st.markdown(f"""
                    <div class="voyager-category-title">
                        <span>{cat}</span>
                        <span class="voyager-tag" style="margin-left: auto; font-size: 0.72rem;">{len(items)} items</span>
                    </div>
                    """, unsafe_allow_html=True)
                    for itm in items:
                        item_key = f"pack_{destination}_{cat}_{itm}"
                        st.checkbox(itm, key=item_key)

    with tab_phrases:
        guide = get_destination_language_guide(destination)
        st.markdown(f"""
        <div style="margin-bottom: 14px;">
            <h3 style="font-size: 1.1rem; font-weight: 600; margin-bottom: 4px;">Local Phrases &amp; Cultural Guide</h3>
            <p style="color: var(--text-muted); font-size: 0.85rem;">Essential communications &amp; customs for traveling in {h(destination)}</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="voyager-weather-hero">
            <div style="display: flex; align-items: center; gap: 18px;">
                <span style="font-size: 2.4rem;">🗣️</span>
                <div>
                    <div style="color: var(--text-muted); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.06em;">Spoken Language</div>
                    <div style="font-size: 1.35rem; font-weight: 700; color: var(--text-primary); margin: 2px 0;">{guide['language']}</div>
                    <div style="color: var(--accent); font-size: 0.85rem; font-weight: 500;">Common Greeting: {guide['greeting']}</div>
                </div>
            </div>
            <div>
                <span class="voyager-tag" style="font-size: 0.78rem;">Script: {guide.get('script', 'Local')}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_left, col_right = st.columns([1.6, 1.2])

        with col_left:
            st.markdown("<div style='font-size: 0.95rem; font-weight: 600; margin-bottom: 10px;'>💬 Handy Travel Phrases</div>", unsafe_allow_html=True)
            for phrase in guide["phrases"]:
                st.markdown(f"""
                <div class="voyager-phrase-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                        <span class="voyager-phrase-english">{phrase['english']}</span>
                        <span class="voyager-tag" style="font-size: 0.7rem; padding: 2px 8px;">{phrase['category']}</span>
                    </div>
                    <div class="voyager-phrase-local">{phrase['local']}</div>
                    <div class="voyager-phrase-phonetic">Pronounce: "{phrase['pronunciation']}"</div>
                </div>
                """, unsafe_allow_html=True)

        with col_right:
            st.markdown("<div style='font-size: 0.95rem; font-weight: 600; margin-bottom: 10px;'>🧭 Local Etiquette &amp; Customs</div>", unsafe_allow_html=True)
            st.markdown("""<div class="voyager-etiquette-card">""", unsafe_allow_html=True)
            for rule in guide["etiquette"]:
                st.markdown(f"<div style='font-size: 0.86rem; color: var(--text-secondary); line-height: 1.6; margin-bottom: 10px;'>{rule}</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("<div style='font-size: 0.95rem; font-weight: 600; margin-top: 18px; margin-bottom: 10px;'>🚨 Emergency Contacts</div>", unsafe_allow_html=True)
            for emer in guide["emergency"]:
                st.markdown(f"""
                <div class="voyager-emergency-item">
                    <span style="font-size: 0.85rem; color: var(--text-secondary);">{emer['service']}</span>
                    <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; font-weight: 600; color: var(--error);">{emer['number']}</span>
                </div>
                """, unsafe_allow_html=True)

    with tab2:
        st.markdown(f"""
        <div style="margin-bottom: 16px;">
            <h3 style="font-size: 1.1rem; font-weight: 600; margin-bottom: 4px;">Places to visit</h3>
            <p style="color: var(--text-muted); font-size: 0.85rem;">Curated based on your interests</p>
        </div>
        """, unsafe_allow_html=True)

        for place in attractions:
            st.markdown(f"""
            <div class="voyager-attraction-item">
                <div class="voyager-attraction-icon">{place['icon']}</div>
                <div>
                    <div style="font-weight: 500; font-size: 0.95rem;">{place['name']}</div>
                    <div style="color: var(--text-muted); font-size: 0.78rem; text-transform: capitalize;">{place['category']}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    with tab3:
        st.markdown(f"""
        <div style="margin-bottom: 16px;">
            <h3 style="font-size: 1.1rem; font-weight: 600; margin-bottom: 4px;">Your itinerary</h3>
            <p style="color: var(--text-muted); font-size: 0.85rem;">Day-by-day plan for {h(destination)}</p>
        </div>
        """, unsafe_allow_html=True)
        st.markdown(itinerary)

    # Action buttons
    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

    pdf = create_pdf(from_location, destination, total_cost, itinerary, flight, hotel, days)
    msg = f"Trip: {h(from_location)} -> {h(destination)} | {days} days | ₹{total_cost:,}"
    share_url = f"https://wa.me/?text={quote(msg)}"

    b1, b2, b3 = st.columns(3)
    with b1:
        st.markdown(f"""
        <a href="{share_url}" target="_blank" style="
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 12px 0;
            background: transparent;
            border: 1px solid var(--border);
            border-radius: 10px;
            color: var(--text-secondary);
            text-decoration: none;
            font-weight: 500;
            font-size: 0.9rem;
            transition: all 0.2s ease;
            width: 100%;
            box-sizing: border-box;
        ">📱 Share</a>
        """, unsafe_allow_html=True)
    with b2:
        st.download_button(
            "⬇ Download PDF",
            data=pdf,
            file_name=f"voyager_trip_{safe_filename(destination)}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    with b3:
        if st.button("↻ New Trip", use_container_width=True):
            st.session_state.pop("results", None)
            st.session_state.chat_history = []
            st.session_state.chat_destination = ""
            st.rerun()

    st.session_state.chat_destination = destination

# ---------------- CHATBOT ----------------
if st.session_state.get("chat_destination"):
    chat_dest = st.session_state.chat_destination

    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)

    st.markdown(f"""
    <div style="
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 24px 28px;
        margin-bottom: 20px;
    ">
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 4px;">
            <span style="font-size: 1.3rem;">💬</span>
            <h3 style="font-size: 1.1rem; font-weight: 600; margin: 0;">Ask about {h(chat_dest)}</h3>
        </div>
        <p style="color: var(--text-muted); font-size: 0.85rem; margin: 0; padding-left: 40px;">
            Local food, hidden gems, cultural tips — ask anything
        </p>
    </div>
    """, unsafe_allow_html=True)

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_input = st.chat_input(f"Ask about {chat_dest}...")

    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        if client:
            try:
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {
                            "role": "system",
                            "content": f"You are an expert travel guide for {chat_dest}. "
                                       f"Help users discover famous places, local food, culture, hidden gems, "
                                       f"and practical travel tips. Keep answers concise and helpful. "
                                       f"Use a warm, knowledgeable tone."
                        },
                        *st.session_state.chat_history
                    ]
                )
                reply = response.choices[0].message.content
            except Exception as e:
                reply = "Sorry, something went wrong while generating a response. Please try again."
        else:
            reply = f"Here are some highlights of {chat_dest}: Local Museum, City Park, Heritage Fort, Food Street, and Botanical Garden. For real-time answers, please configure the Groq API key."

        st.session_state.chat_history.append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.write(reply)

# ---------------- EMPTY STATE ----------------
if not results and not submit:
    st.markdown("""
    <div class="voyager-empty-state">
        <div class="voyager-empty-icon">✦</div>
        <h3 style="font-size: 1.1rem; font-weight: 600; margin-bottom: 8px; color: var(--text-primary);">
            Ready to plan your trip
        </h3>
        <p style="color: var(--text-muted); font-size: 0.9rem; max-width: 400px; margin: 0 auto; line-height: 1.6;">
            Enter your travel details in the sidebar and click <strong style="color: var(--accent);">Plan Trip</strong> to get a personalized itinerary, flight and hotel options, and cost breakdown.
        </p>
    </div>
    """, unsafe_allow_html=True)
