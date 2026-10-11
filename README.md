# Voyager — AI Travel Planner

An AI-powered travel planner built with **Streamlit** and **Groq** (`llama-3.3-70b-versatile`). Enter where you're going, your dates, budget, and interests, and Voyager generates a day-by-day itinerary, flight and hotel estimates, a cost breakdown, and answers follow-up questions about your destination.

## Features

- **AI itinerary generation** — detailed, day-by-day plans tailored to your interests.
- **Flight & hotel estimates** — mock search results with pricing, duration, stops, and ratings.
- **Budget tracking** — automatic cost breakdown (flight, hotel, food, transport) with a color-coded progress bar.
- **Destination chatbot** — ask about local food, hidden gems, culture, and travel tips.
- **PDF export** — download your full itinerary and trip summary as a PDF.
- **Shareable trips** — one-click WhatsApp share of your trip summary.
- **Trip memory** — remembers your last planned trip.
- **Custom dark design system** — a polished, modern UI (see [`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md)).

## Tech Stack

| Layer | Technology |
|-------|------------|
| UI | Streamlit |
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
   venv\Scripts\activate      # Windows
   # source venv/bin/activate # macOS/Linux
   pip install -r requirements.txt
   ```

3. **Add your Groq API key** — create a `.env` file in the project root:
   ```
   GROQ_API_KEY=your_groq_api_key_here
   ```
   Get a key at [console.groq.com](https://console.groq.com). Without a key the app still runs, using fallback/mock content.

4. **Run the app**
   ```bash
   streamlit run travel_planner.py
   ```

## Project Structure

```
.
├── travel_planner.py    # Main Streamlit application
├── DESIGN_SYSTEM.md     # UI design system & tokens
├── travel_memory.json   # Persisted last-trip data
├── requirements.txt     # Python dependencies
└── .gitignore
```

## License

This project is provided as-is for educational and personal use.
