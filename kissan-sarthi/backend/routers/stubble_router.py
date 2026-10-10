"""
Kissan Sarthi — Stubble Router
API endpoints for stubble management, pollution calculation, and eco pledges.
"""

from fastapi import APIRouter, Depends, HTTPException
import aiosqlite

from database import get_db
from models.stubble import StubbleAnalysisRequest, StubblePledgeRequest, StubbleRecordResponse
from services import stubble_service

router = APIRouter(prefix="/api/stubble", tags=["Stubble Management"])


@router.post("/analyze")
async def analyze_stubble(
    request: StubbleAnalysisRequest,
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    Analyze stubble for a harvested crop.
    Returns pollution impact data and eco-friendly alternatives.
    """
    try:
        result = await stubble_service.analyze_stubble(db, request.crop_id, request.stubble_area_acres)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stubble analysis failed: {str(e)}")


@router.post("/pledge")
async def record_pledge(
    request: StubblePledgeRequest,
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    Record a farmer's no-burn pledge.
    Returns pledge certificate data with environmental impact.
    """
    try:
        result = await stubble_service.record_pledge(
            db, request.crop_id, request.stubble_area_acres, request.farmer_choice
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/history/{crop_id}", response_model=list[StubbleRecordResponse])
async def get_stubble_history(crop_id: str, db: aiosqlite.Connection = Depends(get_db)):
    """Get stubble management records for a crop."""
    return await stubble_service.get_stubble_history(db, crop_id)


@router.get("/impact-summary")
async def get_impact_summary(db: aiosqlite.Connection = Depends(get_db)):
    """Get aggregate environmental impact across all farms and pledges."""
    return await stubble_service.get_impact_summary(db)
