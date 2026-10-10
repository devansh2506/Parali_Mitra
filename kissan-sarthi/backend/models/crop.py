"""
Pydantic models for Crop entity — request/response schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class CropType(str, Enum):
    KHARIF = "Kharif"
    RABI = "Rabi"
    ZAID = "Zaid"
    PERENNIAL = "Perennial"


class CropStage(str, Enum):
    SOWING = "Sowing"
    GERMINATION = "Germination"
    VEGETATIVE = "Vegetative"
    FLOWERING = "Flowering"
    MATURITY = "Maturity"
    HARVEST = "Harvest"


class CropStatus(str, Enum):
    ACTIVE = "active"
    HARVESTED = "harvested"
    FAILED = "failed"


class CropCreate(BaseModel):
    """Schema for adding a crop to a farm."""
    farm_id: str = Field(..., description="ID of the farm this crop belongs to")
    crop_name: str = Field(..., min_length=2, max_length=100)
    crop_type: CropType
    variety: Optional[str] = Field(None, max_length=100)
    area_acres: Optional[float] = Field(None, gt=0)
    sowing_date: Optional[str] = Field(None, description="ISO date string YYYY-MM-DD")
    fertilizers_used: Optional[List[str]] = Field(default_factory=list)
    pesticides_used: Optional[List[str]] = Field(default_factory=list)


class CropUpdate(BaseModel):
    """Schema for updating crop details."""
    crop_name: Optional[str] = Field(None, min_length=2, max_length=100)
    crop_type: Optional[CropType] = None
    variety: Optional[str] = None
    area_acres: Optional[float] = Field(None, gt=0)
    sowing_date: Optional[str] = None
    current_stage: Optional[CropStage] = None
    fertilizers_used: Optional[List[str]] = None
    pesticides_used: Optional[List[str]] = None
    status: Optional[CropStatus] = None
    expected_harvest_date: Optional[str] = None


class CropResponse(BaseModel):
    """Schema for crop data in API responses."""
    id: str
    farm_id: str
    crop_name: str
    crop_type: Optional[str] = None
    variety: Optional[str] = None
    area_acres: Optional[float] = None
    sowing_date: Optional[str] = None
    expected_harvest_date: Optional[str] = None
    current_stage: Optional[str] = None
    fertilizers_used: Optional[str] = None
    pesticides_used: Optional[str] = None
    analysis_result: Optional[str] = None
    status: Optional[str] = "active"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    farm_name: Optional[str] = None


class CropAnalysisRequest(BaseModel):
    """Schema for requesting AI crop analysis."""
    crop_id: str
