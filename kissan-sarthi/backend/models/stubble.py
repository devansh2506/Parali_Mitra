"""
Pydantic models for Stubble Management entity — request/response schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional


class StubbleAnalysisRequest(BaseModel):
    """Schema for requesting stubble analysis."""
    crop_id: str = Field(..., description="ID of the harvested crop")
    stubble_area_acres: float = Field(..., gt=0, description="Area with stubble in acres")


class StubblePledgeRequest(BaseModel):
    """Schema for recording a no-burn pledge."""
    crop_id: str
    stubble_area_acres: float = Field(..., gt=0)
    farmer_choice: Optional[str] = Field(None, description="Selected alternative method")


class StubbleRecordResponse(BaseModel):
    """Schema for stubble record in API responses."""
    id: str
    crop_id: str
    stubble_area_acres: Optional[float] = None
    disposal_method: Optional[str] = None
    co2_saved_kg: Optional[float] = 0
    pm25_saved_kg: Optional[float] = 0
    alternatives_shown: Optional[str] = None
    farmer_choice: Optional[str] = None
    impact_summary: Optional[str] = None
    created_at: Optional[str] = None
    crop_name: Optional[str] = None
    farm_name: Optional[str] = None
