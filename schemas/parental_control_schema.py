from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class TransatelParam(BaseModel):
    """Transatel parameter format"""
    name: str = Field(..., description="Parameter name (e.g., BT_AC_ALLOW_ADULT_CONTENT)")
    value: str = Field(..., pattern="^(on|off)$", description="Parameter value: on or off")


class ParentalControlSettings(BaseModel):
    """Parental control settings in Transatel format"""
    params: List[TransatelParam] = Field(..., description="List of Transatel parameters")


class ParentalControlResponse(BaseModel):
    """Response with parental control settings"""
    child_sim_card_id: int
    child_name: str
    sim_number: Optional[str] = None
    iccid: Optional[str] = None
    has_custom_settings: bool
    settings_source: str = Field(..., description="CUSTOM, NOT_SET")
    
    # Settings in Transatel format (can be null if not set)
    params: Optional[List[TransatelParam]] = Field(None, description="Current settings as Transatel parameters")
    previous_params: Optional[List[TransatelParam]] = Field(None, description="Previous settings before last update")
    
    # Metadata
    last_synced_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ParentalControlUpdateRequest(BaseModel):
    """Request to update parental control settings"""
    child_sim_card_id: int
    params: List[TransatelParam] = Field(..., description="Settings to apply")
    sync_with_transatel: bool = Field(True, description="Sync with Transatel API immediately")


class ParentalControlSyncResponse(BaseModel):
    """Response from sync operation"""
    success: bool
    message: str
    params_sent: Optional[List[TransatelParam]] = None
    error: Optional[str] = None
