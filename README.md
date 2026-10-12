# Voyager — AI Travel Planner

![Python](https://img.shields.io/badge/python-3.9%2B-blue?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)
![Groq](https://img.shields.io/badge/AI-Groq-F55036)
![Made with ❤️](https://img.shields.io/badge/made%20with-%E2%9D%A4%EF%B8%8F-6c63ff)

An AI-powered travel planner built with **Streamlit** and **Groq** (`llama-3.3-70b-versatile`). Tell Voyager where you're going, your dates, budget, and interests — it generates a day-by-day itinerary, lets you compare and pick flights and hotels, tracks your budget, and answers follow-up questions about your destination.

## Table of Contents

- [Features](#features)
- [How It Works](#how-it-works)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Roadmap](#roadmap)

## Features

- **AI itinerary generation** — detailed, day-by-day plans tailored to your interests.
- **Interactive 3D Dark Map** — visualizes city center, selected hotel, and attraction pins using Pydeck with interactive hover cards.
- **Live Weather Forecast** — real-time climate conditions, wind speed, and a 5-day forecast with travel tips powered by Open-Meteo.
- **Smart AI Packing Checklist** — dynamic checklist tailored to destination weather, duration, and interests with live completion progress tracking and reset.
- **Local Phrases & Cultural Guide** — destination-aware language greetings, essential phrases with pronunciation, etiquette tips, and emergency contacts.
- **Compare & choose** — pick from multiple flight and hotel options; costs recalculate instantly.
- **Stable results** — search results are deterministic per route (seeded), so they don't shuffle on every interaction.
- **Budget tracking** — automatic cost breakdown (flight, hotel, food, transport) with a color-coded progress bar.
- **Destination chatbot** — ask about local food, hidden gems, culture, and travel tips.
- **PDF export** — download a clean, formatted itinerary and trip summary.
- **Shareable trips** — one-click WhatsApp share with a properly encoded summary.
- **Trip memory** — remembers your last planned trip.
- **Custom dark design system** — a polished, modern UI (see [`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md)).

## How It Works

```
                    ┌─────────────────────┐
   From / To ──────►│                     │
   Dates / Budget ──►│   Streamlit form    │
   Interests ───────►│                     │
                    └──────────┬──────────┘
                               │  Plan Trip
                               ▼
          ┌────────────────────────────────────────┐
          │  search_flights / search_hotels (mock)  │
          │  generate_itinerary  ──►  Groq LLM      │
          │  calculate_total_cost                   │
          └───────────────┬────────────────────────┘
                          ▼
        Overview · Attractions · Itinerary · Chatbot
                    + PDF export · WhatsApp share
```

1. **Mock search** — flights and hotels come from a deterministic mock dataset (seeded by route) so results are consistent.
2. **AI itinerary** — Groq generates a detailed, conversational plan; without an API key it falls back to a sensible template.
3. **Interactive selection** — choose your flight and hotel; the total cost and budget bar update live.
4. **Export & share** — download a PDF or share the summary on WhatsApp.

## Tech Stack

| Layer | Technology |
|-------|------------|
| UI | Streamlit |
| Maps | Pydeck |
| Weather & Geo | Open-Meteo API |
| AI | Groq API (`llama-3.3-70b-versatile`) |
| Data | pandas |
| PDF | ReportLab |
| Config | python-dotenv |

## Getting Started

1. **Clone the repo**
   ```bash
   git clone https://github.com/Lohith-RC/voyager-travel-planner.git
   cd voyager-travel-planner
   ```

2. **Create a virtual environment and install dependencies**
   ```bash
   python -m venv venv
   venv\Scripts\activate        # Windows
   # source venv/bin/activate   # macOS/Linux
   pip install -r requirements.txt
   ```

3. **Add your Groq API key** — create a `.env` file in the project root:
   ```
   GROQ_API_KEY=your_groq_api_key_here
   ```
   Get a key at [console.groq.com](https://console.groq.com). The app still runs without a key, using fallback content.

4. **Run the app**
   ```bash
   streamlit run travel_planner.py
   ```

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | No | Enables AI itinerary generation and the destination chatbot. Without it, Voyager uses fallback content. |

## Project Structure

```
.
├── travel_planner.py    # Main Streamlit application
├── DESIGN_SYSTEM.md     # UI design system & tokens
├── travel_memory.json   # Persisted last-trip data (generated at runtime)
├── requirements.txt     # Python dependencies
└── .gitignore
```

## Roadmap

- [x] Map view of attractions & hotel stays (Pydeck)
- [x] Live destination weather forecasts & advisory (Open-Meteo)
- [x] Smart AI packing checklist with weather & duration adaptation
- [x] Local language phrases, customs & emergency helplines
- [ ] Real flight & hotel data via a travel API
- [ ] Multi-currency support
- [ ] Save and reload multiple trips
- [ ] User accounts

## License

This project is provided as-is for educational and personal use.
