# 🌤️ WeatherGPT — Next-Gen Meteorological Intelligence Platform

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini-4285F4?style=for-the-badge&logo=google)](https://ai.google.dev/)
[![Docker](https://img.shields.io/badge/Deployment-Docker%20%26%20Compose-2496ED?style=for-the-badge&logo=docker)](https://www.docker.com/)
[![Kubernetes](https://img.shields.io/badge/Orchestration-Kubernetes-326CE5?style=for-the-badge&logo=kubernetes)](https://kubernetes.io/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](LICENSE)

**WeatherGPT** is a state-of-the-art meteorological web application that combines live microclimate observations with **Google Gemini AI**. Designed with an editorial luxury dark theme and an authentic Google Gemini-inspired chat studio, WeatherGPT provides real-time atmospheric telemetry, agricultural advisories for farmers, travel microclimate forecasts, and voice-assisted multilingual interactions.

---

## 🌟 Key Features

* **🛰️ Real-Time Microclimate Telemetry**: Synchronizes live weather data (temperature, humidity, wind vectors, precipitation rates, soil metrics, river stages) across Indian regions (Mumbai, Varanasi, Meghalaya, Shimla, etc.) via Open-Meteo APIs.
* **🤖 Google Gemini AI Chat Studio**: Natural conversation engine powered by Google Gemini, capable of instant dynamic geocoding for any city or district worldwide.
* **🌾 Specialized Persona Modes**:
  * **Farmer Mode**: Delivers agro-meteorological advisories, soil moisture insights, and crop protection guidance.
  * **Travel Mode**: Generates transit microclimate warnings and itinerary weather forecasts.
  * **Standard Mode**: Precise general weather analysis and atmospheric breakdowns.
* **🗣️ Voice & Multilingual Integration**: Web Speech API integration supporting voice queries in **English**, **Hindi (हिंदी)**, and **Telugu (తెలుగు)**.
* **📜 Live Marquee Weather Ticker**: Real-time scrolling ticker across key metropolitan zones with auto-pause interaction.
* **🐳 Cloud-Native Deployment**: Containerized with Docker & Docker Compose, and packaged with Kubernetes manifest for cloud infrastructure.

---

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| **Frontend** | Vanilla HTML5, Custom Editorial CSS3, ES6 JavaScript, Web Speech API |
| **Backend API** | Python 3.11+, FastAPI, Uvicorn, Pydantic |
| **AI Intelligence** | Google Gemini API (`google-genai` / `google-generativeai`) |
| **Data Ingestion** | Open-Meteo Weather API & Geocoding API |
| **Containerization** | Docker, Docker Compose, Nginx Alpine |
| **Orchestration** | Kubernetes (`deployment.yaml`) |

---

## 📁 Directory Structure

```
Weather GPT/
├── index.html              # Landing page (Editorial luxury dark theme + 4K atmospheric video)
├── chat.html               # Gemini Chat Studio (Luminous UI, voice input, persona controls)
├── DEV_README.md           # Developer debugging & architecture reference
├── README.md               # Project overview and deployment guide
├── docker-compose.yml      # Orchestrates FastAPI backend and Nginx static frontend
├── styles/
│   ├── landing.css         # Typography, video overlays, tickers, glassmorphic cards
│   └── chat.css            # Gemini chat layout, glow animations, prompt chips
├── scripts/
│   ├── landing.js          # Telemetry sync engine, video switcher, stats counter
│   └── chat.js             # Gemini AI interaction engine, geocoding & speech recognition
├── backend/
│   ├── main.py             # FastAPI entrypoint with CORS & route registration
│   ├── Dockerfile          # Python backend container build definition
│   ├── requirements.txt    # Python dependencies (FastAPI, google-genai, etc.)
│   ├── routes/             # API route handlers (ai.py, weather.py, forecast.py, alerts.py)
│   └── services/           # Business logic & Gemini service integration
└── k8s/
    └── deployment.yaml     # Kubernetes deployment & service specifications
```

---

## 🚀 Quick Start Guide

### Option 1: Run with Docker Compose (Recommended)

The fastest way to launch the complete full-stack environment:

1. **Clone the repository** and navigate to the project directory:
   ```bash
   cd "Weather GPT"
   ```

2. **Configure Environment Variables**:
   Create a `backend/.env` file with your Google Gemini API key:
   ```env
   GEMINI_API_KEY=your_google_gemini_api_key_here
   PORT=8000
   ```

3. **Spin up the stack**:
   ```bash
   docker-compose up --build
   ```

4. **Access the Application**:
   * **Frontend Web Application**: [http://localhost:3000](http://localhost:3000)
   * **FastAPI Backend Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### Option 2: Local Development Setup

#### 1. Start the FastAPI Backend

```bash
# Navigate to backend directory
cd backend

# Create & activate a virtual environment
python3 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file with your API key
echo "GEMINI_API_KEY=your_gemini_api_key_here" > .env

# Run FastAPI server
uvicorn main:app --reload --port 8000
```

#### 2. Start the Frontend Server

```bash
# In the root directory of the project:
python3 -m http.server 3000
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

> [!NOTE]
> Web Speech API (voice recording) requires `localhost` or HTTPS. Avoid opening HTML files directly via `file://`.

---

## 🔌 API Reference Overview

The FastAPI backend provides structured REST endpoints:

| Endpoint | Method | Description |
|---|---|---|
| `GET /` | `GET` | API Health Check |
| `POST /ai/chat` | `POST` | Processes conversational prompts using Google Gemini with weather context |
| `GET /weather` | `GET` | Retrieves current weather telemetry for specified coordinates/city |
| `GET /forecast` | `GET` | Retrieves multi-day meteorological forecast |
| `GET /alerts` | `GET` | Fetches active meteorological weather alerts and severe warnings |

Full interactive API documentation is available at `http://localhost:8000/docs` when running the backend.

---

## ☸️ Kubernetes Deployment

Deploy WeatherGPT to your Kubernetes cluster:

```bash
kubectl apply -f k8s/deployment.yaml
```

Check deployment status:
```bash
kubectl get deployments
kubectl get services
```

---

## 💡 Troubleshooting & Debugging

For developer debugging procedures, state checking, and manual DOM verification scripts, refer to [`DEV_README.md`](file:///Users/sumitsah_03690/Documents/Weather%20GPT/DEV_README.md).

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).
