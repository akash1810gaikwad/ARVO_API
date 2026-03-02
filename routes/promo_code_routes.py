from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from config.mysql_database import get_mysql_db
from services.promo_code_service import promo_code_service
from schemas.promo_code_schema import (
    PromoCodeCreate,
    PromoCodeUpdate,
    PromoCodeResponse,
    PromoCodeValidationResponse
)

router = APIRouter(prefix="/api/v1/promo-codes", tags=["Promo Codes"])


@router.post("/validate/{code}", response_model=PromoCodeValidationResponse)
def validate_promo_code(
    code: str,
    db: Session = Depends(get_mysql_db)
):
    """Validate a promo code"""
    is_valid, message, promo = promo_code_service.validate_promo_code(db, code)
    
    return {
        "valid": is_valid,
        "message": message,
        "promo_code": promo
    }


@router.get("/", response_model=List[PromoCodeResponse])
def get_all_promo_codes(
    active_only: bool = False,
    db: Session = Depends(get_mysql_db)
):
    """Get all promo codes"""
    promos = promo_code_service.get_all_promo_codes(db, active_only)
    return promos


@router.get("/{code}", response_model=PromoCodeResponse)
def get_promo_code(
    code: str,
    db: Session = Depends(get_mysql_db)
):
    """Get a specific promo code by code"""
    promo = promo_code_service.get_promo_code_by_code(db, code)
    if not promo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Promo code not found"
        )
    return promo


@router.post("/", response_model=PromoCodeResponse, status_code=status.HTTP_201_CREATED)
def create_promo_code(
    promo_data: PromoCodeCreate,
    db: Session = Depends(get_mysql_db)
):
    """Create a new promo code"""
    # Check if code already exists
    existing = promo_code_service.get_promo_code_by_code(db, promo_data.code)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Promo code already exists"
        )
    
    promo = promo_code_service.create_promo_code(db, promo_data.model_dump())
    if not promo:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create promo code"
        )
    
    return promo


@router.put("/{code}", response_model=PromoCodeResponse)
def update_promo_code(
    code: str,
    update_data: PromoCodeUpdate,
    db: Session = Depends(get_mysql_db)
):
    """Update an existing promo code"""
    promo = promo_code_service.update_promo_code(
        db, 
        code, 
        update_data.model_dump(exclude_unset=True)
    )
    
    if not promo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Promo code not found"
        )
    
    return promo


@router.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_promo_code(
    code: str,
    db: Session = Depends(get_mysql_db)
):
    """Delete a promo code"""
    success = promo_code_service.delete_promo_code(db, code)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Promo code not found"
        )
    return None
