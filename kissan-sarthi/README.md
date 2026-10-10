# 🌾 Kissan Sarthi (किसान सारथी)

AI-powered farming companion for Indian agriculture: farm land registration, crop growth forecasting, plant disease photo diagnosis, and post-harvest stubble pollution management.

Live URL on Vercel: [https://kissan-sarthi.vercel.app](https://kissan-sarthi.vercel.app)

---

## 🚀 Key Modules

1. **🏡 Farm Land Registration (`/farms`)**:
   - Location details (State, District, Village, Coordinates).
   - Land dimensions & acreage calculation with automated perimeter & area calculation.
   - Soil profiles (8 Indian soil categories) & irrigation system mapping.

2. **🌾 Crop Sowing & AI Care (`/crops`)**:
   - Database of common Indian crops (Wheat, Rice, Sugarcane, Cotton, Mustard, Maize, etc.).
   - Dynamic AI crop analysis with harvest countdown, yield estimation, stage-wise care calendar, weekly nutrient schedule, and pest warnings.

3. **🩺 AI Crop Health Doctor (`/health`)**:
   - Photo upload of diseased leaves/stems with symptom checklists.
   - Multimodal AI pathology diagnosis, severity scoring, organic remedies, safe chemical dosages, and direct Kisan Call Center helpline (1800-180-1551).

4. **♻️ Stubble Management & Clean Air (`/stubble`)**:
   - Interactive carbon & smog pollution savings calculator (CO₂, PM2.5, PM10, trees saved).
   - 5 profitable eco-friendly stubble alternatives (Pusa Bio-Decomposer, Happy Seeder mulching, bio-pellets, mushroom cultivation, enriched fodder).
   - "No-Burn Eco Pledge" generator with official, printable **Eco-Warrior Farmer Certificate** (किसान गौरव प्रमाण पत्र).

---

## 🛠️ Architecture

- **`frontend/`**: Next.js 16 (App Router), Vanilla CSS eco-theme design system, Lucide icons, fullstack serverless API routes (`/api/...`).
- **`backend/`**: Python FastAPI, SQLite (`aiosqlite`), Pydantic models, Google Gemini AI service.

---

## 💻 Local Setup

### Frontend (Next.js)
```bash
cd frontend
npm install
npm run dev
# Running on http://localhost:3000
```

### Backend (FastAPI)
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# API docs at http://localhost:8000/docs
```
