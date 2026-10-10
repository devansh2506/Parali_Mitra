"""
Pydantic models for Health Check entity — request/response schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class SeverityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class HealthCheckCreate(BaseModel):
    """Schema for creating a health check (sent as form data, not JSON)."""
    crop_id: str = Field(..., description="ID of the crop to check")
    symptoms_reported: Optional[str] = Field(None, max_length=500, description="Farmer-described symptoms")


class HealthCheckResponse(BaseModel):
    """Schema for health check data in API responses."""
    id: str
    crop_id: str
    image_path: Optional[str] = None
    symptoms_reported: Optional[str] = None
    diagnosis: Optional[str] = None
    severity: Optional[str] = None
    recommendations: Optional[str] = None
    created_at: Optional[str] = None
    crop_name: Optional[str] = None
    farm_name: Optional[str] = None
