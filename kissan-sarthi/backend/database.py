"""
Kissan Sarthi — Database Module
Manages SQLite connection via aiosqlite and creates tables on startup.
"""

import aiosqlite
from config import DATABASE_PATH

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS farms (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    owner_name TEXT NOT NULL,
    location_state TEXT NOT NULL,
    location_district TEXT,
    location_village TEXT,
    latitude REAL,
    longitude REAL,
    total_area_acres REAL NOT NULL,
    soil_type TEXT,
    irrigation_type TEXT,
    water_source TEXT,
    additional_notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS crops (
    id TEXT PRIMARY KEY,
    farm_id TEXT NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    crop_name TEXT NOT NULL,
    crop_type TEXT CHECK(crop_type IN ('Kharif', 'Rabi', 'Zaid', 'Perennial')),
    variety TEXT,
    area_acres REAL,
    sowing_date TEXT,
    expected_harvest_date TEXT,
    current_stage TEXT DEFAULT 'Sowing',
    fertilizers_used TEXT DEFAULT '[]',
    pesticides_used TEXT DEFAULT '[]',
    analysis_result TEXT,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'harvested', 'failed')),
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS health_checks (
    id TEXT PRIMARY KEY,
    crop_id TEXT NOT NULL REFERENCES crops(id) ON DELETE CASCADE,
    image_path TEXT,
    symptoms_reported TEXT,
    diagnosis TEXT,
    severity TEXT CHECK(severity IN ('low', 'medium', 'high', 'critical')),
    recommendations TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS stubble_records (
    id TEXT PRIMARY KEY,
    crop_id TEXT NOT NULL REFERENCES crops(id),
    stubble_area_acres REAL,
    disposal_method TEXT,
    co2_saved_kg REAL DEFAULT 0,
    pm25_saved_kg REAL DEFAULT 0,
    alternatives_shown TEXT DEFAULT '[]',
    farmer_choice TEXT,
    impact_summary TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


async def get_db() -> aiosqlite.Connection:
    """Get a database connection. Used as a FastAPI dependency."""
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
    finally:
        await db.close()


async def init_db():
    """Initialize database schema on application startup."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript(SCHEMA_SQL)
        await db.commit()
    print(f"✅ Database initialized at {DATABASE_PATH}")
