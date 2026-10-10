"""
Kissan Sarthi — Health Service
Business logic for crop health diagnosis using image analysis.
"""

import os
import uuid
import json
from datetime import datetime
from typing import Optional

import aiosqlite
from PIL import Image

from config import UPLOAD_DIR
from models.health import HealthCheckResponse
from services.gemini_service import gemini_service


MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_DIMENSION = 4096


async def create_health_check(
    db: aiosqlite.Connection,
    crop_id: str,
    image_bytes: bytes,
    filename: str,
    symptoms: Optional[str] = None,
) -> dict:
    """
    Process a health check: save image, run AI diagnosis, store results.
    Returns the complete health check result.
    """
    check_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    # Validate and save image
    image_path = await _save_image(crop_id, check_id, image_bytes, filename)

    # Fetch crop + farm context for AI
    cursor = await db.execute(
        """SELECT c.*, f.location_state, f.location_district, f.name as farm_name
           FROM crops c JOIN farms f ON f.id = c.farm_id
           WHERE c.id = ?""",
        (crop_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        raise ValueError(f"Crop with ID {crop_id} not found")

    context = {
        "crop_name": row["crop_name"],
        "variety": row["variety"],
        "location_state": row["location_state"],
        "location_district": row["location_district"],
        "current_stage": row["current_stage"],
        "symptoms": symptoms or "None reported",
    }

    # Run AI diagnosis
    diagnosis = await gemini_service.diagnose_health(image_path, context)

    diagnosis_json = json.dumps(diagnosis)
    severity = diagnosis.get("severity", "medium")
    recommendations_json = json.dumps(diagnosis.get("treatment_plan", {}))

    # Store in database
    await db.execute(
        """INSERT INTO health_checks (id, crop_id, image_path, symptoms_reported,
           diagnosis, severity, recommendations, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (check_id, crop_id, image_path, symptoms, diagnosis_json, severity, recommendations_json, now),
    )
    await db.commit()

    return {
        "id": check_id,
        "crop_id": crop_id,
        "image_path": image_path,
        "symptoms_reported": symptoms,
        "diagnosis": diagnosis,
        "severity": severity,
        "created_at": now,
        "crop_name": row["crop_name"],
        "farm_name": row["farm_name"],
    }


async def get_health_history(db: aiosqlite.Connection, crop_id: str) -> list[HealthCheckResponse]:
    """Get all health checks for a crop, ordered by most recent."""
    cursor = await db.execute(
        """SELECT h.*, c.crop_name, f.name as farm_name
           FROM health_checks h
           JOIN crops c ON c.id = h.crop_id
           JOIN farms f ON f.id = c.farm_id
           WHERE h.crop_id = ?
           ORDER BY h.created_at DESC""",
        (crop_id,),
    )
    rows = await cursor.fetchall()
    return [_row_to_health_check(row) for row in rows]


async def get_health_check(db: aiosqlite.Connection, check_id: str) -> Optional[dict]:
    """Get a specific health check by ID, with parsed JSON fields."""
    cursor = await db.execute(
        """SELECT h.*, c.crop_name, f.name as farm_name
           FROM health_checks h
           JOIN crops c ON c.id = h.crop_id
           JOIN farms f ON f.id = c.farm_id
           WHERE h.id = ?""",
        (check_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None

    diagnosis = {}
    if row["diagnosis"]:
        try:
            diagnosis = json.loads(row["diagnosis"])
        except json.JSONDecodeError:
            diagnosis = {"raw": row["diagnosis"]}

    return {
        "id": row["id"],
        "crop_id": row["crop_id"],
        "image_path": row["image_path"],
        "symptoms_reported": row["symptoms_reported"],
        "diagnosis": diagnosis,
        "severity": row["severity"],
        "recommendations": row["recommendations"],
        "created_at": row["created_at"],
        "crop_name": row["crop_name"],
        "farm_name": row["farm_name"],
    }


async def _save_image(crop_id: str, check_id: str, image_bytes: bytes, filename: str) -> str:
    """Validate, resize if needed, and save the uploaded image."""
    # Check file size
    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise ValueError(f"Image too large. Maximum size is {MAX_IMAGE_SIZE // (1024*1024)}MB.")

    # Check extension
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Invalid image format. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    # Create directory
    save_dir = os.path.join(UPLOAD_DIR, crop_id)
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, f"{check_id}{ext}")

    # Save original
    with open(save_path, "wb") as f:
        f.write(image_bytes)

    # Resize if too large
    try:
        with Image.open(save_path) as img:
            if max(img.size) > MAX_DIMENSION:
                img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)
                img.save(save_path, quality=85)
    except Exception:
        pass  # If resize fails, keep original

    return save_path


def _row_to_health_check(row: aiosqlite.Row) -> HealthCheckResponse:
    """Convert a database row to HealthCheckResponse model."""
    return HealthCheckResponse(
        id=row["id"],
        crop_id=row["crop_id"],
        image_path=row["image_path"],
        symptoms_reported=row["symptoms_reported"],
        diagnosis=row["diagnosis"],
        severity=row["severity"],
        recommendations=row["recommendations"],
        created_at=row["created_at"],
        crop_name=row["crop_name"] if "crop_name" in row.keys() else None,
        farm_name=row["farm_name"] if "farm_name" in row.keys() else None,
    )
