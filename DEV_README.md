# 🔧 WeatherGPT — Developer Debug & Architecture Reference

> **Developer-Only Guide**: Explains the codebase architecture, live weather synchronization engine, Google Gemini chat interface, and step-by-step debugging procedures.

---

## 1. Project Directory Structure

```
Weather GPT/
├── index.html              ← Landing page (Editorial luxury dark theme + 4K video)
├── chat.html               ← Chat interface (Authentic Google Gemini layout)
├── DEV_README.md           ← Developer debugging reference (this file)
├── sources/                ← High-resolution media assets
│   ├── weather_drone_4k.mov    (4K UHD aerial atmospheric drone scan)
│   ├── monsoon_landscape.mov   (Full-bleed monsoon valley dynamics)
│   ├── mumbai_sea_link.png     (Bandra-Worli Sea Link coastal mist screenshot)
│   ├── varanasi_ghats.png      (Ganges river hydrology station screenshot)
│   ├── valley_fields.png       (Meghalaya terrace agro-weather screenshot)
│   └── cloudy_hills.png        (Sub-Himalayan mountain microclimate screenshot)
├── styles/
│   ├── landing.css         ← Editorial styling, typography, video overlay, marquee
│   └── chat.css            ← Gemini layout, slim icon rail, luminous glow, waveform
└── scripts/
    ├── landing.js          ← Real-time telemetry sync, video switcher, counters
    └── chat.js             ← Gemini interaction engine, live geocoding, voice recognition
```

---

## 2. Real-Time Meteorological Architecture

WeatherGPT connects public observation streams with an LLM conversational layer:

### A. Landing Page — Real-Time Indian Microclimates (`#climates`)
- **Engine**: `scripts/landing.js` → `syncAllClimates()`
- **Endpoints**: Open-Meteo Public WMO Ingestion (`https://api.open-meteo.com/v1/forecast`)
- **Zones Synchronized**:
  1. **Mumbai** (`18.97°N, 72.82°E`): Ambient Temp (`#mumbaiTemp`), Humidity (`#mumbaiHum`), Wind (`#mumbaiWind`), Visibility (`#mumbaiVis`).
  2. **Varanasi** (`25.31°N, 82.97°E`): Ambient Temp (`#varanasiTemp`), Humidity (`#varanasiHum`), Wind (`#varanasiWind`), River Stage (`#varanasiStage`).
  3. **Meghalaya / Shillong** (`25.57°N, 91.88°E`): Valley Temp (`#meghalayaTemp`), Humidity (`#meghalayaHum`), Precip Rate (`#meghalayaRain`), Agro Soil (`#meghalayaSoil`).
  4. **Shimla** (`31.10°N, 77.17°E`): Highland Temp (`#shimlaTemp`), Humidity (`#shimlaHum`), Wind Vector (`#shimlaWind`), Windchill (`#shimlaApparent`).
- **Fail-Safe Fallback**: If offline or blocked, `fetchZoneWeather()` catches errors and gracefully retains the official IMD baseline telemetry without throwing or breaking layout.

### B. Landing Page — Live National Weather Marquee (`#liveWeatherTicker`)
- **Location**: Right beneath `#hero` and above `.stats-strip`.
- **Display**: Seamless infinite scrolling ticker across 8 key Indian cities (New Delhi, Mumbai, Bengaluru, Kolkata, Chennai, Hyderabad, Shimla, Shillong).
- **Control**: Pauses automatically on hover (`animation-play-state: paused`).

### C. Chat Interface — Dynamic Geocoding & Telemetry Fetching
- **Engine**: `scripts/chat.js` → `generateResponseAsync()`
- **Pipeline**:
  1. **Direct Cache Lookup**: Rapid match for 30+ major Indian cities in `weatherData` dictionary.
  2. **Dynamic Live Geocoding**: If an unlisted town or district is queried (e.g. "Solapur weather", "temperature in Thrissur"), `fetchLiveCityWeather(cityName)` resolves latitude & longitude via `https://geocoding-api.open-meteo.com/v1/search` and fetches real-time telemetry.
  3. **WMO Weather Code Interpreter**: Maps WMO codes (0 to 99) to clear conditions (Clear Sky, Radiation Fog, Drizzle, Continuous Rainfall, Thunderstorms) with relevant icons.
  4. **Multi-Mode Context**: Injects Agro-meteorological advisories in **Farmer Mode** and transit advisories in **Travel Mode**.
  5. **Multilingual Synthesis**: Outputs responses in authentic Hindi, Telugu, or English.

---

## 3. How to Run Locally

```bash
# In project root:
python3 -m http.server 3000
# Open http://localhost:3000 in your browser
```

> [!NOTE]
> Web Speech API (voice recording) and Clipboard API require `localhost` or HTTPS. Never open as `file://`.

---

## 4. Developer Debugging Table

| Symptom | Primary Suspect | Where to Look / How to Fix |
|---|---|---|
| Climate card numbers show static fallback | Network / API blocked | Open DevTools Console: Look for `[LiveWeatherSync]`. Check Network tab for `api.open-meteo.com`. Click **Sync Live** button. |
| Hero video not playing | Autoplay policy / Path | Check `#bgVideo` source in `index.html`. Local server MUST be running (browser blocks video on `file://`). |
| Video switcher doesn't switch | Missing ID / element | In `landing.js`, check `btnVidDrone` and `btnVidMonsoon` click handlers. |
| Chat send button stays disabled | Input listener | Check `updateSendBtnState()` in `chat.js`. Requires non-empty input. |
| AI response stuck on typing dots | Unhandled JS exception | Check Console for uncaught errors. In console run `state.isTyping = false` to unlock. |
| Voice recording doesn't activate | Mic permission / Browser | Web Speech API requires Chrome/Edge/Safari and `http://localhost`. Check site microphone permissions. |
| City not found in chat | Query parsing | `extractCityFromQuery(q)` extracts city names from phrases like "weather in X". Test via Console: `fetchLiveCityWeather('Nashik')`. |

---

## 5. Console Quick Sanity Checks

### Check Landing Page Elements (run on `index.html`):
```js
console.log({
  navbar: !!document.getElementById('navbar'),
  heroVideo: !!document.getElementById('bgVideo'),
  liveTicker: !!document.getElementById('liveWeatherTicker'),
  statsStrip: !!document.getElementById('statsStrip'),
  climatesSection: !!document.getElementById('climates'),
  mumbaiTemp: document.getElementById('mumbaiTemp')?.textContent,
  varanasiTemp: document.getElementById('varanasiTemp')?.textContent,
  meghalayaTemp: document.getElementById('meghalayaTemp')?.textContent,
  shimlaTemp: document.getElementById('shimlaTemp')?.textContent,
});
```

### Test Live City Weather Fetching (run on `chat.html`):
```js
// Test live dynamic geocoding for any Indian city:
fetchLiveCityWeather('Nagpur').then(res => console.log('Nagpur Live Data:', res));
fetchLiveCityWeather('Kochi').then(res => console.log('Kochi Live Data:', res));
```
