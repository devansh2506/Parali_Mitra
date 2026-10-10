"""
Kissan Sarthi — Health Router
API endpoints for crop health diagnosis via image upload.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional
import aiosqlite

from database import get_db
from models.health import HealthCheckResponse
from services import health_service

router = APIRouter(prefix="/api/health", tags=["Health"])


@router.post("/check")
async def create_health_check(
    crop_id: str = Form(...),
    symptoms_reported: Optional[str] = Form(None),
    image: UploadFile = File(...),
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    Upload a crop image and get AI-powered health diagnosis.
    Accepts multipart form data with image file and crop context.
    """
    # Read image bytes
    image_bytes = await image.read()

    try:
        result = await health_service.create_health_check(
            db=db,
            crop_id=crop_id,
            image_bytes=image_bytes,
            filename=image.filename or "image.jpg",
            symptoms=symptoms_reported,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/history/{crop_id}", response_model=list[HealthCheckResponse])
async def get_health_history(crop_id: str, db: aiosqlite.Connection = Depends(get_db)):
    """Get all health check records for a crop."""
    return await health_service.get_health_history(db, crop_id)


@router.get("/{check_id}")
async def get_health_check(check_id: str, db: aiosqlite.Connection = Depends(get_db)):
    """Get a specific health check result with full diagnosis."""
    result = await health_service.get_health_check(db, check_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Health check not found")
    return result
