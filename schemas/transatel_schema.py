from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

# Enums for search filter values
class LineStatus(str, Enum):
    ACTIVE = "Active"
    SUSPENDED = "Suspended"
    AVAILABLE = "Available"
    TERMINATED = "Terminated"

class GroupName(str, Enum):
    CHARITY = "Charity"
    E2E_TEST_TSL = "E2E_TEST_TSL"
    HIS = "HIS"
    HIBS = "HIBS"
    ROVERS = "Rovers"
    Arvo = 'Arvo'

class BusinessEntity(str, Enum):
    MVNA_UK_EEL_ACQUA_TELECOM = "MVNA_UK_EEL_ACQUA_TELECOM"
    # Add more business entities if needed

class SortOrder(str, Enum):
    ASC = "ASC"
    DESC = "DESC"

class SortFieldName(str, Enum):
    TRANSATEL_ID = "transatelId"
    MSISDN = "msisdn"
    ICCID = "iccId"
    LINE_STATUS = "lineStatus"
    ACTIVATION_DATE = "activationDate"

class SubscriberOption(BaseModel):
    name: str
    value: str

class ActivateSubscriberRequest(BaseModel):
    ratePlan: str
    externalReference: str
    group: str
    subscriberCountryOfResidence: str
    options:Optional[List[SubscriberOption]] = None


class BulkActivateSubscriberRequest(BaseModel):
    """Bulk activation request for up to 10 ICCIDs"""
    iccids: List[str] = Field(..., min_items=1, max_items=10, description="List of ICCIDs to activate (max 10)")
    ratePlan: str = Field(..., description="Rate plan for all SIMs")
    externalReference: str = Field(..., description="External reference (will be used as base, ICCID appended)")
    group: str = Field(..., description="Group name for all SIMs")
    subscriberCountryOfResidence: str = Field(..., description="Country of residence for all subscribers")
    options: Optional[List[SubscriberOption]] = Field(None, description="Options for all SIMs")


class BulkActivationResult(BaseModel):
    """Result for a single SIM activation in bulk"""
    iccid: str
    success: bool
    message: str
    data: Optional[dict] = None
    error: Optional[str] = None


class BulkActivateSubscriberResponse(BaseModel):
    """Response for bulk activation"""
    total_requested: int
    successful: int
    failed: int
    results: List[BulkActivationResult]

    
class ModifySubscriberRequest(BaseModel):
    ratePlan: str = Field(..., max_length=50)
    group: Optional[str] = Field(None, max_length=50)
    options: Optional[List[SubscriberOption]] = None


class SuspendSubscriberRequest(BaseModel):
    ratePlan: str = Field(..., max_length=50)

class ReactivateSubscriberRequest(BaseModel):
    ratePlan: str = Field(..., max_length=50)

class SimSwapRequest(BaseModel):
    newSimSerial: str = Field(...)
    ratePlan: str = Field(..., max_length=50)

class TerminateSubscriberRequest(BaseModel):
    ratePlan: str = Field(..., max_length=50)

class PortingSubscriberRequest(BaseModel):
    portabilityMsisdn: str = Field(..., max_length=20)
    authorizationCode: dict = Field(..., description="Authorization code details")
    wishedPortabilityDate: str = Field(..., description="Desired portability date in YYYY-MM-DD format")


class SubscriberContactInfo(BaseModel):
    """Subscriber contact/personal info for Transatel update-contact-info API"""
    pointOfSale: Optional[str] = Field(None, description="Point of sale identifier")
    title: Optional[str] = Field(None, max_length=10, description="Title (Mr, Mrs, Ms, etc.)")
    firstName: Optional[str] = Field(None, max_length=100, description="First name")
    lastName: Optional[str] = Field(None, max_length=100, description="Last name")
    dateOfBirth: Optional[str] = Field(None, description="Date of birth (YYYY-MM-DD)")
    company: Optional[str] = Field(None, max_length=200, description="Company name")
    address: Optional[str] = Field(None, max_length=500, description="Street address")
    zipCode: Optional[str] = Field(None, max_length=20, description="Zip/postal code")
    city: Optional[str] = Field(None, max_length=100, description="City")
    country: Optional[str] = Field(None, max_length=3, description="Country code (ISO 3166-1 alpha-3, e.g. FRA, GBR)")
    contactEmail: Optional[str] = Field(None, max_length=255, description="Contact email address")


class UpdateContactInfoRequest(BaseModel):
    """Request body for PUT /subscribers/sim-serial/{sim_serial}/contact-info"""
    ratePlan: str = Field(..., max_length=50, description="Rate plan code")
    subscriberInfo: SubscriberContactInfo = Field(..., description="Subscriber personal/contact information")


# Search API Schemas
class SearchFilter(BaseModel):
    type: str = Field(..., description="Filter type, e.g., 'ValueFilter'")
    fieldName: str = Field(..., description="Field name to filter on")
    allowedValues: List[str] = Field(..., description="List of allowed values")

class SortField(BaseModel):
    fieldName: str = Field(..., description="Field name to sort by")
    sortOrder: str = Field(..., description="Sort order: ASC or DESC")

class SearchLinesRequest(BaseModel):
    query: Optional[str] = Field("", description="Search query string")
    page: int = Field(0, ge=0, description="Page number (0-based)")
    size: int = Field(200, ge=1, le=1000, description="Page size")
    filters: List[SearchFilter] = Field(default_factory=list, description="List of filters")
    sortField: Optional[SortField] = Field(None, description="Sort configuration")
    aggregationFields: List[str] = Field(default_factory=list, description="Aggregation fields")
    nestedAggregationFields: List[str] = Field(default_factory=list, description="Nested aggregation fields")

class SearchLinesResponse(BaseModel):
    success: bool
    data: dict
    total_count: Optional[int] = None
    page: int
    size: int

# Simplified search request with enums
class SimpleSearchFilter(BaseModel):
    """Simplified search filter with predefined enum values"""
    lineStatus: Optional[List[LineStatus]] = Field(None, description="Filter by line status")
    group: Optional[List[GroupName]] = Field(None, description="Filter by group name")
    businessEntity: Optional[List[BusinessEntity]] = Field(None, description="Filter by business entity")

class SimpleSortField(BaseModel):
    """Sort configuration with dropdown values"""
    fieldName: SortFieldName = Field(SortFieldName.TRANSATEL_ID, description="Field to sort by")
    sortOrder: SortOrder = Field(SortOrder.ASC, description="Sort order")

class SimpleSearchRequest(BaseModel):
    """Simplified search request with dropdown values"""
    page: int = Field(0, ge=0, description="Page number (0-based)")
    size: int = Field(200, ge=1, le=1000, description="Page size")
    query: Optional[str] = Field("", description="Search query string")
    filters: Optional[SimpleSearchFilter] = Field(None, description="Search filters with dropdown values")
    sortField: Optional[SimpleSortField] = Field(None, description="Sort configuration with dropdown values")