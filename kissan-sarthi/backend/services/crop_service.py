"""
Kissan Sarthi — Crop Service
Business logic for crop management and AI analysis.
"""

import uuid
import json
from datetime import datetime
from typing import Optional

import aiosqlite

from models.crop import CropCreate, CropUpdate, CropResponse
from services.gemini_service import gemini_service


async def create_crop(db: aiosqlite.Connection, crop: CropCreate) -> CropResponse:
    """Create a new crop record for a farm."""
    crop_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    fertilizers_json = json.dumps(crop.fertilizers_used or [])
    pesticides_json = json.dumps(crop.pesticides_used or [])

    await db.execute(
        """INSERT INTO crops (id, farm_id, crop_name, crop_type, variety, area_acres,
           sowing_date, current_stage, fertilizers_used, pesticides_used, status,
           created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'Sowing', ?, ?, 'active', ?, ?)""",
        (
            crop_id, crop.farm_id, crop.crop_name, crop.crop_type.value if crop.crop_type else None,
            crop.variety, crop.area_acres, crop.sowing_date,
            fertilizers_json, pesticides_json, now, now,
        ),
    )
    await db.commit()

    return await get_crop_by_id(db, crop_id)


async def get_crops_by_farm(db: aiosqlite.Connection, farm_id: str) -> list[CropResponse]:
    """Retrieve all crops for a specific farm."""
    cursor = await db.execute(
        """SELECT c.*, f.name as farm_name FROM crops c
           JOIN farms f ON f.id = c.farm_id
           WHERE c.farm_id = ? ORDER BY c.created_at DESC""",
        (farm_id,),
    )
    rows = await cursor.fetchall()
    return [_row_to_crop(row) for row in rows]


async def get_all_crops(db: aiosqlite.Connection) -> list[CropResponse]:
    """Retrieve all crops across all farms."""
    cursor = await db.execute(
        """SELECT c.*, f.name as farm_name FROM crops c
           JOIN farms f ON f.id = c.farm_id
           ORDER BY c.created_at DESC"""
    )
    rows = await cursor.fetchall()
    return [_row_to_crop(row) for row in rows]


async def get_crop_by_id(db: aiosqlite.Connection, crop_id: str) -> Optional[CropResponse]:
    """Retrieve a single crop by ID."""
    cursor = await db.execute(
        """SELECT c.*, f.name as farm_name FROM crops c
           JOIN farms f ON f.id = c.farm_id
           WHERE c.id = ?""",
        (crop_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return _row_to_crop(row)


async def update_crop(db: aiosqlite.Connection, crop_id: str, crop: CropUpdate) -> Optional[CropResponse]:
    """Update an existing crop record."""
    existing = await get_crop_by_id(db, crop_id)
    if existing is None:
        return None

    update_data = crop.model_dump(exclude_none=True)
    if not update_data:
        return existing

    # Serialize lists to JSON
    if "fertilizers_used" in update_data:
        update_data["fertilizers_used"] = json.dumps(update_data["fertilizers_used"])
    if "pesticides_used" in update_data:
        update_data["pesticides_used"] = json.dumps(update_data["pesticides_used"])
    if "crop_type" in update_data:
        update_data["crop_type"] = update_data["crop_type"].value if hasattr(update_data["crop_type"], "value") else update_data["crop_type"]
    if "current_stage" in update_data:
        update_data["current_stage"] = update_data["current_stage"].value if hasattr(update_data["current_stage"], "value") else update_data["current_stage"]
    if "status" in update_data:
        update_data["status"] = update_data["status"].value if hasattr(update_data["status"], "value") else update_data["status"]

    update_data["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in update_data.keys())
    values = list(update_data.values()) + [crop_id]

    await db.execute(f"UPDATE crops SET {set_clause} WHERE id = ?", values)
    await db.commit()

    return await get_crop_by_id(db, crop_id)


async def delete_crop(db: aiosqlite.Connection, crop_id: str) -> bool:
    """Delete a crop record."""
    cursor = await db.execute("DELETE FROM crops WHERE id = ?", (crop_id,))
    await db.commit()
    return cursor.rowcount > 0


async def analyze_crop(db: aiosqlite.Connection, crop_id: str) -> dict:
    """Run AI analysis on a crop. Fetches farm context and calls Gemini."""
    # Fetch crop with farm info
    cursor = await db.execute(
        """SELECT c.*, f.location_state, f.location_district, f.soil_type,
                  f.irrigation_type, f.total_area_acres, f.name as farm_name
           FROM crops c JOIN farms f ON f.id = c.farm_id
           WHERE c.id = ?""",
        (crop_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None

    farm_data = {
        "location_state": row["location_state"],
        "location_district": row["location_district"],
        "soil_type": row["soil_type"],
        "irrigation_type": row["irrigation_type"],
        "total_area_acres": row["total_area_acres"],
    }
    crop_data = {
        "crop_name": row["crop_name"],
        "crop_type": row["crop_type"],
        "variety": row["variety"],
        "area_acres": row["area_acres"],
        "sowing_date": row["sowing_date"],
        "current_stage": row["current_stage"],
        "fertilizers_used": row["fertilizers_used"],
        "pesticides_used": row["pesticides_used"],
    }

    # Call Gemini AI
    analysis = await gemini_service.analyze_crop(farm_data, crop_data)

    # Cache the result in the database
    analysis_json = json.dumps(analysis)
    await db.execute(
        "UPDATE crops SET analysis_result = ?, updated_at = ? WHERE id = ?",
        (analysis_json, datetime.utcnow().isoformat(), crop_id),
    )
    await db.commit()

    return analysis


async def get_crop_analysis(db: aiosqlite.Connection, crop_id: str) -> Optional[dict]:
    """Get cached analysis result for a crop."""
    cursor = await db.execute(
        "SELECT analysis_result FROM crops WHERE id = ?", (crop_id,)
    )
    row = await cursor.fetchone()
    if row is None or row["analysis_result"] is None:
        return None
    return json.loads(row["analysis_result"])


def _row_to_crop(row: aiosqlite.Row) -> CropResponse:
    """Convert a database row to CropResponse model."""
    return CropResponse(
        id=row["id"],
        farm_id=row["farm_id"],
        crop_name=row["crop_name"],
        crop_type=row["crop_type"],
        variety=row["variety"],
        area_acres=row["area_acres"],
        sowing_date=row["sowing_date"],
        expected_harvest_date=row["expected_harvest_date"],
        current_stage=row["current_stage"],
        fertilizers_used=row["fertilizers_used"],
        pesticides_used=row["pesticides_used"],
        analysis_result=row["analysis_result"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        farm_name=row["farm_name"] if "farm_name" in row.keys() else None,
    )
