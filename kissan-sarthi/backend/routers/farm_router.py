"""
Kissan Sarthi — Farm Router
API endpoints for farm CRUD operations.
"""

from fastapi import APIRouter, Depends, HTTPException
import aiosqlite

from database import get_db
from models.farm import FarmCreate, FarmUpdate, FarmResponse
from services import farm_service

router = APIRouter(prefix="/api/farms", tags=["Farms"])


@router.post("", response_model=FarmResponse, status_code=201)
async def create_farm(farm: FarmCreate, db: aiosqlite.Connection = Depends(get_db)):
    """Register a new farm."""
    return await farm_service.create_farm(db, farm)


@router.get("", response_model=list[FarmResponse])
async def list_farms(db: aiosqlite.Connection = Depends(get_db)):
    """List all registered farms."""
    return await farm_service.get_all_farms(db)


@router.get("/{farm_id}", response_model=FarmResponse)
async def get_farm(farm_id: str, db: aiosqlite.Connection = Depends(get_db)):
    """Get details of a specific farm."""
    farm = await farm_service.get_farm_by_id(db, farm_id)
    if farm is None:
        raise HTTPException(status_code=404, detail="Farm not found")
    return farm


@router.put("/{farm_id}", response_model=FarmResponse)
async def update_farm(farm_id: str, farm: FarmUpdate, db: aiosqlite.Connection = Depends(get_db)):
    """Update farm details."""
    updated = await farm_service.update_farm(db, farm_id, farm)
    if updated is None:
        raise HTTPException(status_code=404, detail="Farm not found")
    return updated


@router.delete("/{farm_id}")
async def delete_farm(farm_id: str, db: aiosqlite.Connection = Depends(get_db)):
    """Delete a farm and all its associated data."""
    deleted = await farm_service.delete_farm(db, farm_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Farm not found")
    return {"message": "Farm deleted successfully", "id": farm_id}
