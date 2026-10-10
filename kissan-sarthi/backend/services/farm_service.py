"""
Kissan Sarthi — Farm Service
Business logic for farm CRUD operations.
"""

import uuid
from datetime import datetime
from typing import Optional

import aiosqlite

from models.farm import FarmCreate, FarmUpdate, FarmResponse


async def create_farm(db: aiosqlite.Connection, farm: FarmCreate) -> FarmResponse:
    """Create a new farm record."""
    farm_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    await db.execute(
        """INSERT INTO farms (id, name, owner_name, location_state, location_district,
           location_village, latitude, longitude, total_area_acres, soil_type,
           irrigation_type, water_source, additional_notes, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            farm_id, farm.name, farm.owner_name, farm.location_state,
            farm.location_district, farm.location_village,
            farm.latitude, farm.longitude, farm.total_area_acres,
            farm.soil_type, farm.irrigation_type, farm.water_source,
            farm.additional_notes, now, now,
        ),
    )
    await db.commit()

    return FarmResponse(
        id=farm_id, name=farm.name, owner_name=farm.owner_name,
        location_state=farm.location_state, location_district=farm.location_district,
        location_village=farm.location_village, latitude=farm.latitude,
        longitude=farm.longitude, total_area_acres=farm.total_area_acres,
        soil_type=farm.soil_type, irrigation_type=farm.irrigation_type,
        water_source=farm.water_source, additional_notes=farm.additional_notes,
        created_at=now, updated_at=now, crop_count=0,
    )


async def get_all_farms(db: aiosqlite.Connection) -> list[FarmResponse]:
    """Retrieve all farms with crop counts."""
    cursor = await db.execute(
        """SELECT f.*, COUNT(c.id) as crop_count
           FROM farms f LEFT JOIN crops c ON c.farm_id = f.id
           GROUP BY f.id ORDER BY f.created_at DESC"""
    )
    rows = await cursor.fetchall()
    return [_row_to_farm(row) for row in rows]


async def get_farm_by_id(db: aiosqlite.Connection, farm_id: str) -> Optional[FarmResponse]:
    """Retrieve a single farm by ID."""
    cursor = await db.execute(
        """SELECT f.*, COUNT(c.id) as crop_count
           FROM farms f LEFT JOIN crops c ON c.farm_id = f.id
           WHERE f.id = ? GROUP BY f.id""",
        (farm_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return _row_to_farm(row)


async def update_farm(db: aiosqlite.Connection, farm_id: str, farm: FarmUpdate) -> Optional[FarmResponse]:
    """Update an existing farm record. Only updates non-None fields."""
    existing = await get_farm_by_id(db, farm_id)
    if existing is None:
        return None

    update_data = farm.model_dump(exclude_none=True)
    if not update_data:
        return existing

    update_data["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in update_data.keys())
    values = list(update_data.values()) + [farm_id]

    await db.execute(f"UPDATE farms SET {set_clause} WHERE id = ?", values)
    await db.commit()

    return await get_farm_by_id(db, farm_id)


async def delete_farm(db: aiosqlite.Connection, farm_id: str) -> bool:
    """Delete a farm and all its associated data (cascades)."""
    cursor = await db.execute("DELETE FROM farms WHERE id = ?", (farm_id,))
    await db.commit()
    return cursor.rowcount > 0


def _row_to_farm(row: aiosqlite.Row) -> FarmResponse:
    """Convert a database row to FarmResponse model."""
    return FarmResponse(
        id=row["id"],
        name=row["name"],
        owner_name=row["owner_name"],
        location_state=row["location_state"],
        location_district=row["location_district"],
        location_village=row["location_village"],
        latitude=row["latitude"],
        longitude=row["longitude"],
        total_area_acres=row["total_area_acres"],
        soil_type=row["soil_type"],
        irrigation_type=row["irrigation_type"],
        water_source=row["water_source"],
        additional_notes=row["additional_notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        crop_count=row["crop_count"] if "crop_count" in row.keys() else 0,
    )
