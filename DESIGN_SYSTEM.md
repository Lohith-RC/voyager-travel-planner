# Voyager — Design System

## Design Philosophy

The redesign transforms the default Streamlit travel planner into **Voyager** — a sleek, dark-themed travel assistant with a refined visual identity. The design prioritizes clarity, modern typography, and a cohesive dark color system.

## Typography

| Role | Font | Weight | Size |
|------|------|--------|------|
| Display / H1 | DM Sans | 700 (Bold) | 2.4rem |
| Section Headers | DM Sans | 600 (SemiBold) | 1.1rem |
| Body | DM Sans | 400 (Regular) | 0.95rem |
| Labels / Tags | DM Sans | 500 (Medium) | 0.8rem |
| Monospace / Prices | JetBrains Mono | 500 | 1.1rem |

**Why DM Sans:** Geometric, clean, modern — gives the app a tech-forward feel without being generic. Paired with JetBrains Mono for numeric data to ensure price figures align cleanly.

## Color System

### Dark Theme Palette

| Token | Hex | Usage |
|-------|-----|-------|
| `bg-primary` | `#0c0f14` | App background |
| `bg-secondary` | `#131720` | Sidebar, secondary surfaces |
| `bg-tertiary` | `#1a1f2b` | Input fields, hover states |
| `bg-card` | `#161b26` | Cards, metrics, chat bubbles |
| `bg-hover` | `#1e2433` | Interactive hover states |
| `accent` | `#6c63ff` | Primary action, links, highlights |
| `accent-soft` | `rgba(108, 99, 255, 0.12)` | Tag backgrounds, focus rings |
| `accent-glow` | `rgba(108, 99, 255, 0.25)` | Hover glow effects |
| `text-primary` | `#e8eaf0` | Main text |
| `text-secondary` | `#8b90a0` | Subtitles, descriptions |
| `text-muted` | `#555b6e` | Labels, metadata |
| `border` | `#1f2537` | Card borders, dividers |
| `border-subtle` | `#1a1f2a` | Subtle separators |
| `success` | `#34d399` | Under-budget indicator |
| `warning` | `#fbbf24` | Near-budget indicator |
| `error` | `#f87171` | Over-budget, validation errors |

### Accent Usage
- Single accent color (`#6c63ff`) — purple-tinted indigo
- Used sparingly: primary button, links, focus rings, active states
- Glow effects on hover (box-shadow with accent-soft)

## Component Patterns

### Metric Cards
- Dark background with subtle 1px border
- Hover: border shifts to accent color + subtle glow
- Labels: uppercase, small, muted
- Values: large, semi-bold, primary text color
- Tags below: pill-shaped with accent-soft background

### Trip Summary Banner
- Gradient background (card → tertiary)
- Route displayed prominently with arrow icon
- Duration and budget in monospace font
- Budget color-coded: green (under), yellow (near), red (over)

### Budget Progress Bar
- Full-width bar with gradient fill
- Color transitions based on percentage
- Monospace percentage display

### Tab System
- Pill-style tabs with background container
- Active tab: elevated surface with subtle shadow
- Hover: smooth color transition

### Attraction Cards
- Left icon (emoji) + name layout
- Hover: border highlights, background shift
- Rounded container with consistent padding

### Chat Interface
- Card wrapper with title and description
- Standard Streamlit chat bubbles inside
- Rounded corners on all messages

### Weather Hero & Forecast Cards
- Hero banner with current temperature in JetBrains Mono (`2rem`), condition, wind speed, and AI travel advisory
- 5-day forecast grid with responsive cards, micro-elevation hover effect, max/min temperature, and weather emojis

### Interactive Map & Legend
- Pydeck 3D Dark-mode map integrated directly into Streamlit
- ScatterplotLayer + TextLayer with custom dark tooltip
- Color-coded pins: Gold (Destination Center), Purple/Accent (Chosen Hotel), Emerald (Recommended Attractions)
- Map legend bar with colored dots and clear labeling

### Smart Packing Checklist
- 2-column responsive layout with categorized cards (Documents, Clothing, Weather Gear, Tech, Toiletries, Interests)
- Live completion status banner with dynamic progress bar and completion percentage
- One-click reset functionality

### Local Phrases & Cultural Guide
- Language banner with primary tongue, script badge, and customary greeting
- Multi-column phrase cards with English prompt, local script in bold, phonetic pronunciation, and category badge
- Etiquette & customs container with clear bullet points
- Emergency contacts strip with highlighted helpline numbers

### Empty State
- Centered layout with dashed border
- Large icon + descriptive text
- Clear call-to-action reference

## Interactions & Motion

| Element | Transition | Duration |
|---------|-----------|----------|
| Buttons | background-color, box-shadow, transform | 200ms ease |
| Metric cards | border-color, box-shadow | 200ms ease |
| Weather cards | transform translateY(-2px), border-color, box-shadow | 200ms ease |
| Phrase cards | transform translateY(-2px), border-color | 200ms ease |
| Tabs | background-color, color | 200ms ease |
| Attraction items | border-color, background | 200ms ease |
| Text inputs | border-color, box-shadow | 200ms ease |
| Download button | background-color, box-shadow | 200ms ease |
| Plan button | translateY(-1px) on hover | 200ms ease |

## Layout

- Max-width container: 1200px
- Sidebar: dedicated form area with vertical spacing
- Main content: full-width with consistent padding
- Tabs: horizontal, evenly distributed (Overview, Map, Weather, Packing, Phrases, Attractions, Itinerary)
- Metric grid: 4-column equal-width (Flight, Hotel, Climate, Total Cost)
- Action buttons: 3-column equal-width

## Key Design Decisions

1. **No emojis in primary UI elements** — Clean text badge `✦ Voyager Travel`
2. **Monospace for prices & temperatures** — JetBrains Mono ensures numeric alignment
3. **Color-coded budget & pins** — Instant visual feedback on costs and map landmarks
4. **Card-based information** — Every data point lives in a defined container
5. **Real-time Context** — Live weather & 3D dark map give instant spatial and climate awareness
6. **Empty state by default** — Guides users when no trip is planned
7. **Sidebar form improvements** — Date inputs side-by-side, placeholder text, better spacing
