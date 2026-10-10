"""
Kissan Sarthi — Stubble Service
Business logic for stubble management, pollution calculation, and eco alternatives.
"""

import uuid
import json
from datetime import datetime
from typing import Optional

import aiosqlite

from models.stubble import StubbleRecordResponse
from services.gemini_service import gemini_service


async def analyze_stubble(db: aiosqlite.Connection, crop_id: str, area_acres: float) -> dict:
    """
    Analyze stubble for a harvested crop.
    Calculates pollution impact and provides eco-friendly alternatives.
    """
    # Fetch crop + farm context
    cursor = await db.execute(
        """SELECT c.*, f.location_state, f.location_district, f.name as farm_name
           FROM crops c JOIN farms f ON f.id = c.farm_id
           WHERE c.id = ?""",
        (crop_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        raise ValueError(f"Crop with ID {crop_id} not found")

    crop_data = {
        "crop_name": row["crop_name"],
        "crop_type": row["crop_type"],
        "location_state": row["location_state"],
        "location_district": row["location_district"],
    }

    # Run AI analysis
    analysis = await gemini_service.analyze_stubble(crop_data, area_acres)

    # Store the analysis record
    record_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    pollution = analysis.get("pollution_if_burned", {})
    co2_saved = pollution.get("co2_kg", 0)
    pm25_saved = pollution.get("pm25_kg", 0)
    alternatives_json = json.dumps(analysis.get("eco_alternatives", []))

    await db.execute(
        """INSERT INTO stubble_records (id, crop_id, stubble_area_acres,
           co2_saved_kg, pm25_saved_kg, alternatives_shown, impact_summary, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            record_id, crop_id, area_acres, co2_saved, pm25_saved,
            alternatives_json, json.dumps(analysis), now,
        ),
    )
    await db.commit()

    return {
        "id": record_id,
        "crop_id": crop_id,
        "crop_name": row["crop_name"],
        "farm_name": row["farm_name"],
        "stubble_area_acres": area_acres,
        "analysis": analysis,
        "created_at": now,
    }


async def record_pledge(
    db: aiosqlite.Connection,
    crop_id: str,
    area_acres: float,
    farmer_choice: Optional[str] = None,
) -> dict:
    """Record a farmer's no-burn pledge and chosen alternative."""
    # Fetch crop info
    cursor = await db.execute(
        """SELECT c.crop_name, f.name as farm_name, f.owner_name
           FROM crops c JOIN farms f ON f.id = c.farm_id WHERE c.id = ?""",
        (crop_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        raise ValueError(f"Crop with ID {crop_id} not found")

    record_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    # Estimate saved pollution (using rice straw defaults)
    crop_name = row["crop_name"].lower()
    is_wheat = "wheat" in crop_name or "गेहूं" in crop_name
    co2_per_acre = 1780 if is_wheat else 2225
    pm25_per_acre = 5.6 if is_wheat else 7.0
    co2_saved = round(co2_per_acre * area_acres, 1)
    pm25_saved = round(pm25_per_acre * area_acres, 1)

    await db.execute(
        """INSERT INTO stubble_records (id, crop_id, stubble_area_acres,
           disposal_method, co2_saved_kg, pm25_saved_kg, farmer_choice, created_at)
           VALUES (?, ?, ?, 'no-burn-pledge', ?, ?, ?, ?)""",
        (record_id, crop_id, area_acres, co2_saved, pm25_saved, farmer_choice, now),
    )
    await db.commit()

    return {
        "id": record_id,
        "certificate_id": record_id,
        "crop_id": crop_id,
        "crop_name": row["crop_name"],
        "farm_name": row["farm_name"],
        "owner_name": row["owner_name"],
        "farmer_name": row["owner_name"],
        "stubble_area_acres": area_acres,
        "co2_saved_kg": co2_saved,
        "pm25_saved_kg": pm25_saved,
        "farmer_choice": farmer_choice,
        "pledge_date": now,
        "equivalent_trees": round(co2_saved / 22),
        "message": "🌱 Thank you for your pledge! Your decision helps keep the air clean for millions.",
    }


async def get_stubble_history(db: aiosqlite.Connection, crop_id: str) -> list[StubbleRecordResponse]:
    """Get all stubble records for a crop."""
    cursor = await db.execute(
        """SELECT s.*, c.crop_name, f.name as farm_name
           FROM stubble_records s
           JOIN crops c ON c.id = s.crop_id
           JOIN farms f ON f.id = c.farm_id
           WHERE s.crop_id = ?
           ORDER BY s.created_at DESC""",
        (crop_id,),
    )
    rows = await cursor.fetchall()
    return [_row_to_stubble(row) for row in rows]


async def get_impact_summary(db: aiosqlite.Connection) -> dict:
    """Get aggregate environmental impact across all farms."""
    cursor = await db.execute(
        """SELECT
              COUNT(*) as total_records,
              COALESCE(SUM(co2_saved_kg), 0) as total_co2_saved,
              COALESCE(SUM(pm25_saved_kg), 0) as total_pm25_saved,
              COALESCE(SUM(stubble_area_acres), 0) as total_area_saved,
              COUNT(CASE WHEN disposal_method = 'no-burn-pledge' THEN 1 END) as total_pledges
           FROM stubble_records"""
    )
    row = await cursor.fetchone()

    total_co2 = row["total_co2_saved"] or 0
    return {
        "total_records": row["total_records"] or 0,
        "total_co2_saved_kg": round(total_co2, 1),
        "total_pm25_saved_kg": round(row["total_pm25_saved"] or 0, 1),
        "total_area_saved_acres": round(row["total_area_saved"] or 0, 1),
        "total_pledges": row["total_pledges"] or 0,
        "equivalent_trees": round(total_co2 / 60) if total_co2 > 0 else 0,
        "equivalent_car_days": round(total_co2 / 12.1) if total_co2 > 0 else 0,
    }


def _row_to_stubble(row: aiosqlite.Row) -> StubbleRecordResponse:
    """Convert a database row to StubbleRecordResponse model."""
    return StubbleRecordResponse(
        id=row["id"],
        crop_id=row["crop_id"],
        stubble_area_acres=row["stubble_area_acres"],
        disposal_method=row["disposal_method"],
        co2_saved_kg=row["co2_saved_kg"],
        pm25_saved_kg=row["pm25_saved_kg"],
        alternatives_shown=row["alternatives_shown"],
        farmer_choice=row["farmer_choice"],
        impact_summary=row["impact_summary"],
        created_at=row["created_at"],
        crop_name=row["crop_name"] if "crop_name" in row.keys() else None,
        farm_name=row["farm_name"] if "farm_name" in row.keys() else None,
    )
