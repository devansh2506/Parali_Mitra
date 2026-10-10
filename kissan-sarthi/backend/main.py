"""
Kissan Sarthi — Main Application Entry Point
FastAPI application with CORS, lifespan events, and router registration.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import FRONTEND_URL, UPLOAD_DIR
from database import init_db
from routers import farm_router, crop_router, health_router, stubble_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    await init_db()
    print("🌾 Kissan Sarthi API is ready!")
    yield
    # Shutdown
    print("👋 Shutting down Kissan Sarthi API...")


app = FastAPI(
    title="Kissan Sarthi API",
    description="🌾 AI-powered farming assistant for Indian farmers — crop analysis, health diagnosis, and stubble management.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS Middleware ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static Files (uploaded images) ──
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# ── Register Routers ──
app.include_router(farm_router.router)
app.include_router(crop_router.router)
app.include_router(health_router.router)
app.include_router(stubble_router.router)


@app.get("/")
async def root():
    """API root — health check endpoint."""
    return {
        "name": "Kissan Sarthi API",
        "version": "1.0.0",
        "status": "healthy",
        "message": "🌾 Welcome to Kissan Sarthi — Your AI Farming Companion!",
        "docs": "/docs",
    }


@app.get("/api/reference-data/states")
async def get_states():
    """Get list of Indian states for dropdowns."""
    return {
        "states": [
            "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
            "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
            "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
            "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
            "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
            "Delhi", "Jammu & Kashmir", "Ladakh", "Puducherry", "Chandigarh",
        ]
    }


@app.get("/api/reference-data/soil-types")
async def get_soil_types():
    """Get soil types reference data."""
    return {
        "soil_types": [
            {"id": "alluvial", "name": "Alluvial Soil", "name_hi": "जलोढ़ मिट्टी", "icon": "🏔️", "regions": ["Punjab", "UP", "Bihar", "West Bengal"]},
            {"id": "black", "name": "Black Soil", "name_hi": "काली मिट्टी", "icon": "⬛", "regions": ["Maharashtra", "MP", "Gujarat"]},
            {"id": "red", "name": "Red Soil", "name_hi": "लाल मिट्टी", "icon": "🟥", "regions": ["Tamil Nadu", "Karnataka", "Odisha"]},
            {"id": "laterite", "name": "Laterite Soil", "name_hi": "लैटेराइट मिट्टी", "icon": "🟫", "regions": ["Kerala", "Assam", "Karnataka"]},
            {"id": "desert", "name": "Desert/Arid Soil", "name_hi": "मरुस्थली मिट्टी", "icon": "🏜️", "regions": ["Rajasthan", "Gujarat"]},
            {"id": "mountain", "name": "Mountain Soil", "name_hi": "पर्वतीय मिट्टी", "icon": "⛰️", "regions": ["Uttarakhand", "HP", "J&K"]},
            {"id": "peaty", "name": "Peaty/Marshy Soil", "name_hi": "दलदली मिट्टी", "icon": "🌿", "regions": ["Kerala", "West Bengal"]},
            {"id": "saline", "name": "Saline Soil", "name_hi": "लवणीय मिट्टी", "icon": "🧂", "regions": ["Rajasthan", "Gujarat", "Punjab"]},
        ]
    }


@app.get("/api/reference-data/crops")
async def get_crops():
    """Get common Indian crops reference data."""
    return {
        "crops": [
            {"name": "Wheat", "name_hi": "गेहूं", "type": "Rabi", "duration_days": "120-150", "icon": "🌾"},
            {"name": "Rice", "name_hi": "चावल", "type": "Kharif", "duration_days": "90-150", "icon": "🍚"},
            {"name": "Sugarcane", "name_hi": "गन्ना", "type": "Perennial", "duration_days": "300-365", "icon": "🎋"},
            {"name": "Cotton", "name_hi": "कपास", "type": "Kharif", "duration_days": "150-180", "icon": "☁️"},
            {"name": "Mustard", "name_hi": "सरसों", "type": "Rabi", "duration_days": "110-140", "icon": "🌻"},
            {"name": "Maize", "name_hi": "मक्का", "type": "Kharif", "duration_days": "80-110", "icon": "🌽"},
            {"name": "Potato", "name_hi": "आलू", "type": "Rabi", "duration_days": "75-120", "icon": "🥔"},
            {"name": "Tomato", "name_hi": "टमाटर", "type": "Rabi", "duration_days": "60-80", "icon": "🍅"},
            {"name": "Onion", "name_hi": "प्याज", "type": "Rabi", "duration_days": "120-150", "icon": "🧅"},
            {"name": "Soybean", "name_hi": "सोयाबीन", "type": "Kharif", "duration_days": "90-120", "icon": "🫘"},
            {"name": "Groundnut", "name_hi": "मूंगफली", "type": "Kharif", "duration_days": "100-130", "icon": "🥜"},
            {"name": "Chickpea", "name_hi": "चना", "type": "Rabi", "duration_days": "90-120", "icon": "🫘"},
            {"name": "Turmeric", "name_hi": "हल्दी", "type": "Kharif", "duration_days": "240-300", "icon": "🟡"},
            {"name": "Bajra", "name_hi": "बाजरा", "type": "Kharif", "duration_days": "70-90", "icon": "🌾"},
            {"name": "Jowar", "name_hi": "ज्वार", "type": "Kharif", "duration_days": "90-120", "icon": "🌾"},
            {"name": "Barley", "name_hi": "जौ", "type": "Rabi", "duration_days": "110-130", "icon": "🌾"},
            {"name": "Lentil", "name_hi": "मसूर", "type": "Rabi", "duration_days": "90-120", "icon": "🫘"},
            {"name": "Green Gram", "name_hi": "मूंग", "type": "Kharif", "duration_days": "60-75", "icon": "🫛"},
            {"name": "Black Gram", "name_hi": "उड़द", "type": "Kharif", "duration_days": "75-90", "icon": "🫘"},
            {"name": "Pigeon Pea", "name_hi": "अरहर/तूर", "type": "Kharif", "duration_days": "150-270", "icon": "🫛"},
        ]
    }


if __name__ == "__main__":
    import uvicorn
    from config import HOST, PORT
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
