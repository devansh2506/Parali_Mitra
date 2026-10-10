"""
Pydantic models for Farm entity — request/response schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional


class FarmCreate(BaseModel):
    """Schema for creating a new farm."""
    name: str = Field(..., min_length=3, max_length=100, description="Farm name")
    owner_name: str = Field(..., min_length=2, max_length=100, description="Farmer's name")
    location_state: str = Field(..., description="State name")
    location_district: Optional[str] = Field(None, max_length=100)
    location_village: Optional[str] = Field(None, max_length=100)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    total_area_acres: float = Field(..., gt=0, le=10000, description="Total area in acres")
    soil_type: Optional[str] = None
    irrigation_type: Optional[str] = None
    water_source: Optional[str] = Field(None, max_length=200)
    additional_notes: Optional[str] = Field(None, max_length=500)


class FarmUpdate(BaseModel):
    """Schema for updating farm details. All fields are optional."""
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    owner_name: Optional[str] = Field(None, min_length=2, max_length=100)
    location_state: Optional[str] = None
    location_district: Optional[str] = None
    location_village: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    total_area_acres: Optional[float] = Field(None, gt=0, le=10000)
    soil_type: Optional[str] = None
    irrigation_type: Optional[str] = None
    water_source: Optional[str] = None
    additional_notes: Optional[str] = None


class FarmResponse(BaseModel):
    """Schema for farm data in API responses."""
    id: str
    name: str
    owner_name: str
    location_state: str
    location_district: Optional[str] = None
    location_village: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    total_area_acres: float
    soil_type: Optional[str] = None
    irrigation_type: Optional[str] = None
    water_source: Optional[str] = None
    additional_notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    crop_count: int = 0
