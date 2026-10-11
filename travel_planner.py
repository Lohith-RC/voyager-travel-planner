import os
import json
import random
import pandas as pd
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
def search_flights(from_location, destination):
    return random.choice([
        {"Airline": "IndiGo", "Price (₹)": 4500, "Duration": "2h 15m", "Stops": "Non-stop"},
        {"Airline": "Air India", "Price (₹)": 5500, "Duration": "2h 30m", "Stops": "Non-stop"},
        {"Airline": "Vistara", "Price (₹)": 6200, "Duration": "2h 45m", "Stops": "1 Stop"},
    ])

def search_hotels(days):
    per_day = random.randint(1800, 3000)
    return {
        "Hotel Name": "Grand Palace Hotel",
        "Rating": "4.2",
        "Price/Day (₹)": per_day,
        "Total Cost (₹)": per_day * days,
    }

def search_attractions(interests):
    db = {
        "nature": ["Lake View", "National Park", "Botanical Garden"],
        "food": ["Food Street", "Cafe Tour", "Local Restaurant"],
        "history": ["Museum", "Fort", "Temple"],
        "adventure": ["Trekking", "Boating", "Adventure Park"],
    }
    attractions = []
    for i in interests:
        attractions.extend(db.get(i.lower(), []))
    return attractions if attractions else ["City Walk", "Local Market"]

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
def create_pdf(from_location, destination, total_cost, itinerary, flight, hotel, days):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()
    content = []

    content.append(Paragraph("Voyager — Travel Itinerary", styles["Title"]))
    content.append(Spacer(1, 10))
    content.append(Paragraph(f"<b>Route:</b> {from_location} → {destination}", styles["Normal"]))
    content.append(Paragraph(f"<b>Duration:</b> {days} days", styles["Normal"]))
    content.append(Paragraph(f"<b>Estimated Cost:</b> ₹{total_cost:,}", styles["Normal"]))
    content.append(Spacer(1, 10))
    content.append(Paragraph("<b>Flight:</b> {} — ₹{}".format(flight['Airline'], flight['Price (₹)']), styles["Normal"]))
    content.append(Paragraph("<b>Hotel:</b> {} — ₹{:,}".format(hotel['Hotel Name'], hotel['Total Cost (₹)']), styles["Normal"]))
    content.append(Spacer(1, 15))
    content.append(Paragraph("<b>Itinerary</b>", styles["Heading2"]))
    content.append(Spacer(1, 5))

    for line in itinerary.split("\n"):
        if line.strip():
            content.append(Paragraph(line, styles["Normal"]))

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
            <span style="color: var(--text-primary); font-weight: 500;">{memory.get('last_from', '—')} → {dest}</span>
            <span style="color: var(--text-muted); font-size: 0.8rem; margin-left: 8px;">
                {' · '.join(memory.get('last_interests', []))}
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

    from_location = st.text_input("From", placeholder="e.g. Mumbai")
    destination = st.text_input("Destination", placeholder="e.g. Jaipur")

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
        st.error("Please enter both locations to continue.")
    elif start_date > end_date:
        st.error("End date must be after start date.")
    else:
        with st.spinner("Planning your trip..."):
            days = (end_date - start_date).days + 1
            flight = search_flights(from_location, destination)
            hotel = search_hotels(days)
            attractions = search_attractions(interests)
            itinerary = generate_itinerary(
                from_location, destination,
                str(start_date), str(end_date), interests
            )
            total_cost = calculate_total_cost(
                flight["Price (₹)"], hotel["Total Cost (₹)"], days
            )

        save_memory(from_location, destination, interests,
                     f"{start_date} — {end_date}", budget)

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
                    {from_location}
                    <span style="color: var(--accent); margin: 0 10px;">→</span>
                    {destination}
                </div>
            </div>
            <div style="display: flex; gap: 24px; align-items: center;">
                <div style="text-align: center;">
                    <div style="color: var(--text-muted); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em;">Duration</div>
                    <div style="font-family: 'JetBrains Mono', monospace; font-size: 1.1rem; font-weight: 600;">{days}d</div>
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
        tab1, tab2, tab3 = st.tabs(["Overview", "Attractions", "Itinerary"])

        with tab1:
            c1, c2, c3 = st.columns(3)
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
                </div>
                """, unsafe_allow_html=True)
            with c3:
                st.metric("💰 Total Cost", f"₹{total_cost:,}", f"{days} days")
                st.markdown(f"""
                <div style="display: flex; gap: 8px; margin-top: -8px;">
                    <span class="voyager-tag">Food ₹{days * 800:,}</span>
                    <span class="voyager-tag">Transport ₹{days * 500:,}</span>
                </div>
                """, unsafe_allow_html=True)

        with tab2:
            st.markdown(f"""
            <div style="margin-bottom: 16px;">
                <h3 style="font-size: 1.1rem; font-weight: 600; margin-bottom: 4px;">Places to visit</h3>
                <p style="color: var(--text-muted); font-size: 0.85rem;">Curated based on your interests</p>
            </div>
            """, unsafe_allow_html=True)

            icons = {"nature": "🌿", "food": "🍜", "history": "🏛", "adventure": "⛰️"}
            for place in attractions:
                icon = "📍"
                for cat, cat_icon in icons.items():
                    if cat in place.lower() or any(c in place.lower() for c in ["park", "garden", "lake", "food", "cafe", "restaurant", "museum", "fort", "temple", "trek", "boat"]):
                        icon = cat_icon
                        break
                st.markdown(f"""
                <div class="voyager-attraction-item">
                    <div class="voyager-attraction-icon">{icon}</div>
                    <div>
                        <div style="font-weight: 500; font-size: 0.95rem;">{place}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        with tab3:
            st.markdown(f"""
            <div style="margin-bottom: 16px;">
                <h3 style="font-size: 1.1rem; font-weight: 600; margin-bottom: 4px;">Your itinerary</h3>
                <p style="color: var(--text-muted); font-size: 0.85rem;">Day-by-day plan for {destination}</p>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(itinerary)

        # Action buttons
        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

        pdf = create_pdf(from_location, destination, total_cost, itinerary, flight, hotel, days)
        msg = f"Trip: {from_location} → {destination} | {days} days | ₹{total_cost:,}"

        b1, b2, b3 = st.columns(3)
        with b1:
            st.markdown(f"""
            <a href="https://wa.me/?text={msg}" target="_blank" style="
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
                file_name=f"voyager_trip_{destination}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        with b3:
            if st.button("↻ New Trip", use_container_width=True):
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
            <h3 style="font-size: 1.1rem; font-weight: 600; margin: 0;">Ask about {chat_dest}</h3>
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
                reply = f"Something went wrong — {str(e)}"
        else:
            reply = f"Here are some highlights of {chat_dest}: Local Museum, City Park, Heritage Fort, Food Street, and Botanical Garden. For real-time answers, please configure the Groq API key."

        st.session_state.chat_history.append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.write(reply)

# ---------------- EMPTY STATE ----------------
if not submit and not st.session_state.get("chat_destination"):
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
