"""
Kissan Sarthi — Crop Router
API endpoints for crop management and AI analysis.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import aiosqlite

from database import get_db
from models.crop import CropCreate, CropUpdate, CropResponse
from services import crop_service

router = APIRouter(prefix="/api/crops", tags=["Crops"])


@router.post("", response_model=CropResponse, status_code=201)
async def create_crop(crop: CropCreate, db: aiosqlite.Connection = Depends(get_db)):
    """Add a new crop to a farm."""
    result = await crop_service.create_crop(db, crop)
    if result is None:
        raise HTTPException(status_code=400, detail="Failed to create crop")
    return result


@router.get("", response_model=list[CropResponse])
async def list_crops(
    farm_id: Optional[str] = Query(None, description="Filter by farm ID"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """List crops. Optionally filter by farm_id."""
    if farm_id:
        return await crop_service.get_crops_by_farm(db, farm_id)
    return await crop_service.get_all_crops(db)


@router.get("/{crop_id}", response_model=CropResponse)
async def get_crop(crop_id: str, db: aiosqlite.Connection = Depends(get_db)):
    """Get details of a specific crop."""
    crop = await crop_service.get_crop_by_id(db, crop_id)
    if crop is None:
        raise HTTPException(status_code=404, detail="Crop not found")
    return crop


@router.put("/{crop_id}", response_model=CropResponse)
async def update_crop(crop_id: str, crop: CropUpdate, db: aiosqlite.Connection = Depends(get_db)):
    """Update crop details."""
    updated = await crop_service.update_crop(db, crop_id, crop)
    if updated is None:
        raise HTTPException(status_code=404, detail="Crop not found")
    return updated


@router.delete("/{crop_id}")
async def delete_crop(crop_id: str, db: aiosqlite.Connection = Depends(get_db)):
    """Delete a crop record."""
    deleted = await crop_service.delete_crop(db, crop_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Crop not found")
    return {"message": "Crop deleted successfully", "id": crop_id}


@router.post("/{crop_id}/analyze")
async def analyze_crop(crop_id: str, db: aiosqlite.Connection = Depends(get_db)):
    """Trigger AI analysis for a crop. Returns detailed analysis."""
    result = await crop_service.analyze_crop(db, crop_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Crop not found")
    return {"crop_id": crop_id, "analysis": result}


@router.get("/{crop_id}/analysis")
async def get_crop_analysis(crop_id: str, db: aiosqlite.Connection = Depends(get_db)):
    """Get cached AI analysis for a crop."""
    analysis = await crop_service.get_crop_analysis(db, crop_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="No analysis found. Run /analyze first.")
    return {"crop_id": crop_id, "analysis": analysis}
