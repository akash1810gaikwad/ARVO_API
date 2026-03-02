from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List
from config.mysql_database import get_mysql_db
from services.transatel_service import TransatelService

from schemas.transatel_schema import (
    ActivateSubscriberRequest, 
    ModifySubscriberRequest, 
    PortingSubscriberRequest, 
    ReactivateSubscriberRequest, 
    SimSwapRequest, 
    SuspendSubscriberRequest, 
    TerminateSubscriberRequest, 
    UpdateContactInfoRequest,
    SimpleSearchRequest,
    BulkActivateSubscriberRequest,
    BulkActivateSubscriberResponse,
    BulkActivationResult
)
import logging


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/transatel", tags=["Transatel"])

service = TransatelService()


# External API configuration
EXTERNAL_API_BASE_URL = "https://bhnet.uk/api/v1.3/managed-lines"
EXTERNAL_API_TOKEN_URL = "https://bhnet.uk/api/auth/token"  # Adjust as needed


@router.post("/login")
def transatel_login(db: Session = Depends(get_mysql_db)):
    """
    Login to Transatel using main credentials.
    Token is stored in DB and reused automatically.
    Call this endpoint if you get 401 errors to refresh the token.
    """
    try:
        # Clear any existing tokens first
        from repositories.transatel_token_repo import clear_tokens
        clear_tokens(db)
        logger.info("Cleared existing tokens, requesting new token...")
        
        token = service.login(db)
        return {
            "success": True,
            "message": "Authenticated successfully",
            "access_token": token[:10] + "****",
            "credentials": "main",
            "token_length": len(token)
        }
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail={
                "success": False,
                "message": "Authentication failed",
                "error": str(e)
            }
        )


@router.get("/token/status")
def check_token_status(db: Session = Depends(get_mysql_db)):
    """
    Check current token status - useful for debugging 401 errors
    """
    try:
        from repositories.transatel_token_repo import get_valid_token
        from datetime import datetime
        
        token = get_valid_token(db)
        
        if token:
            time_remaining = (token.expires_at - datetime.utcnow()).total_seconds()
            return {
                "success": True,
                "has_valid_token": True,
                "token_type": token.token_type,
                "expires_at": token.expires_at.isoformat(),
                "time_remaining_seconds": int(time_remaining),
                "time_remaining_minutes": round(time_remaining / 60, 2),
                "token_preview": token.access_token[:10] + "****"
            }
        else:
            return {
                "success": True,
                "has_valid_token": False,
                "message": "No valid token found. Call POST /api/v1/transatel/login to authenticate."
            }
    except Exception as e:
        logger.error(f"Error checking token status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to check token status",
                "error": str(e)
            }
        )


@router.get("/esim/{sim_serial}")
def get_esim(sim_serial: str, db: Session = Depends(get_mysql_db)):
    """
    Get eSIM details by SIM serial number.
    """
    try:
        data = service.get_esim_by_sim_serial(db, sim_serial)
        return {
            "success": True,
            "data": data
        }
    except Exception as e:
        error_payload = e.args[0] if isinstance(e.args[0], dict) else str(e)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to fetch eSIM details",
                "error": error_payload
            }
        )


@router.post("/esim/bulk")
def get_multiple_esims(sim_serials: list[str], db: Session = Depends(get_mysql_db)):
    """
    Get eSIM details for multiple SIM serial numbers.
    Accepts an array of SIM serials and returns their details.
    Also generates QR codes from LPA activation codes and saves them as images.
    
    Request body: ["89443042334118130770", "89443042334118130771", ...]
    """
    import os
    from datetime import datetime
    from app.utils.qr_generator import generate_qr_code
    
    try:
        if not sim_serials:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": "SIM serials array cannot be empty",
                    "error": "No SIM serials provided"
                }
            )
        
        if len(sim_serials) > 50:  # Limit to prevent abuse
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": "Too many SIM serials requested",
                    "error": f"Maximum 50 SIM serials allowed, got {len(sim_serials)}"
                }
            )
        
        # Create QR codes folder if it doesn't exist
        qr_folder = "qr_codes"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        batch_folder = os.path.join(qr_folder, f"batch_{timestamp}")
        os.makedirs(batch_folder, exist_ok=True)
        
        results = []
        errors = []
        qr_codes_generated = []
        
        logger.info(f"Processing bulk eSIM request for {len(sim_serials)} SIM serials")
        logger.info(f"QR codes will be saved to: {batch_folder}")
        
        for sim_serial in sim_serials:
            try:
                # Get eSIM details for each SIM serial
                data = service.get_esim_by_sim_serial(db, sim_serial)
                
                # Extract LPA activation code from qrCode.value
                lpa_code = None
                qr_file_path = None
                
                if isinstance(data, dict) and "qrCode" in data and "value" in data["qrCode"]:
                    lpa_code = data["qrCode"]["value"]
                    
                    # Generate QR code image
                    try:
                        qr_bytes = generate_qr_code(lpa_code, size=300)
                        
                        # Save QR code as image file
                        qr_filename = f"{sim_serial}_qr.png"
                        qr_file_path = os.path.join(batch_folder, qr_filename)
                        
                        with open(qr_file_path, 'wb') as f:
                            f.write(qr_bytes)
                        
                        qr_codes_generated.append({
                            "sim_serial": sim_serial,
                            "lpa_code": lpa_code,
                            "qr_file": qr_file_path,
                            "filename": qr_filename
                        })
                        
                        logger.info(f"Generated QR code for {sim_serial}: {qr_file_path}")
                        
                    except Exception as qr_error:
                        logger.error(f"Failed to generate QR code for {sim_serial}: {qr_error}")
                
                # Add QR code info to the result
                result_data = {
                    "sim_serial": sim_serial,
                    "success": True,
                    "data": data,
                    "qr_code_generated": lpa_code is not None,
                    "qr_file_path": qr_file_path,
                    "lpa_code": lpa_code
                }
                
                results.append(result_data)
                logger.info(f"Successfully retrieved eSIM data for {sim_serial}")
                
            except Exception as e:
                error_payload = e.args[0] if isinstance(e.args[0], dict) else str(e)
                error_entry = {
                    "sim_serial": sim_serial,
                    "success": False,
                    "error": error_payload,
                    "qr_code_generated": False,
                    "qr_file_path": None,
                    "lpa_code": None
                }
                results.append(error_entry)
                errors.append(error_entry)
                logger.warning(f"Failed to retrieve eSIM data for {sim_serial}: {error_payload}")
        
        # Calculate success statistics
        successful_count = len([r for r in results if r["success"]])
        failed_count = len(errors)
        qr_generated_count = len(qr_codes_generated)
        
        return {
            "success": True,
            "message": f"Processed {len(sim_serials)} SIM serials: {successful_count} successful, {failed_count} failed",
            "total_requested": len(sim_serials),
            "successful_count": successful_count,
            "failed_count": failed_count,
            "qr_codes_generated": qr_generated_count,
            "qr_folder": batch_folder,
            "results": results,
            "qr_codes": qr_codes_generated,
            "errors": errors if errors else None
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions (validation errors)
        raise
    except Exception as e:
        logger.error(f"Bulk eSIM request failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Bulk eSIM request failed",
                "error": str(e)
            }
        )


@router.get("/subscriber/sim-serial/{sim_serial}")
def get_subscriber_by_sim_serial(sim_serial: str, db: Session = Depends(get_mysql_db)):
    try:
        data = service.get_subscriber_by_sim_serial(db, sim_serial)
        return {
            "success": True,
            "sim_serial": sim_serial,
            "data": data
        }
    except Exception as e:
        error_payload = e.args[0] if isinstance(e.args[0], dict) else str(e)

        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "message": "Failed to fetch subscriber details",
                "error": error_payload
            }
        )

@router.get("/subscriber/msisdn/{msisdn}")
def get_subscriber_by_msisdn(msisdn: str, db: Session = Depends(get_mysql_db)):
    try:
        data = service.get_subscriber_by_msisdn(db, msisdn)
        return {
            "success": True,
            "msisdn": msisdn,
            "data": data
        }
    except Exception as e:
        error_payload = e.args[0] if isinstance(e.args[0], dict) else str(e)

        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "message": "Failed to fetch subscriber details",
                "error": error_payload
            }
        )

@router.post("/subscriber/sim-serial/{sim_serial}/activate")
def activate_subscriber(
    sim_serial: str,
    payload: ActivateSubscriberRequest,
    db: Session = Depends(get_mysql_db),
):
    try:
        # Call Transatel API to activate subscriber
        data = service.activate_subscriber_by_sim_serial(
            db=db,
            sim_serial=sim_serial,
            payload=payload.dict(),
        )

        return {
            "success": True,
            "sim_serial": sim_serial,
            "data": data,
        }
        
    except Exception as e:
        error_payload = e.args[0] if e.args and isinstance(e.args[0], dict) else str(e)
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "message": "Failed to activate subscriber",
                "error": error_payload,
            },
        )


@router.post("/subscriber/bulk-activate", response_model=BulkActivateSubscriberResponse)
def bulk_activate_subscribers(
    payload: BulkActivateSubscriberRequest,
    db: Session = Depends(get_mysql_db),
):
    """
    Bulk activate up to 10 SIMs with the same payload.
    Only the sim_serial (ICCID) changes for each activation.
    
    Example payload:
    {
        "iccids": ["89443042334118128480", "89443042334118129470"],
        "ratePlan": "ROVERS_PLAN_1GB",
        "externalReference": "BULK_ACTIVATION",
        "group": "Rovers",
        "subscriberCountryOfResidence": "GB",
        "options": [
            {"name": "CIRCLE", "value": "on"},
            {"name": "ENABLE", "value": "on"}
        ]
    }
    """
    try:
        results = []
        successful = 0
        failed = 0
        
        logger.info(f"Starting bulk activation for {len(payload.iccids)} ICCIDs")
        
        for iccid in payload.iccids:
            try:
                # Create activation payload for this ICCID
                activation_payload = {
                    "ratePlan": payload.ratePlan,
                    "externalReference": f"{payload.externalReference}_{iccid}",
                    "group": payload.group,
                    "subscriberCountryOfResidence": payload.subscriberCountryOfResidence,
                }
                
                if payload.options:
                    activation_payload["options"] = [opt.dict() for opt in payload.options]
                
                # Call Transatel API to activate subscriber
                data = service.activate_subscriber_by_sim_serial(
                    db=db,
                    sim_serial=iccid,
                    payload=activation_payload,
                )
                                
                # Success
                results.append(BulkActivationResult(
                    iccid=iccid,
                    success=True,
                    message="Activation successful",
                    data=data
                ))
                successful += 1
                logger.info(f"Successfully activated ICCID: {iccid}")
                
            except Exception as e:
                # Failure for this ICCID
                error_msg = str(e)
                if hasattr(e, 'args') and e.args and isinstance(e.args[0], dict):
                    error_msg = str(e.args[0])
                
                results.append(BulkActivationResult(
                    iccid=iccid,
                    success=False,
                    message="Activation failed",
                    error=error_msg
                ))
                failed += 1
                logger.error(f"Failed to activate ICCID {iccid}: {error_msg}")
        
        logger.info(f"Bulk activation completed: {successful} successful, {failed} failed")
        
        return BulkActivateSubscriberResponse(
            total_requested=len(payload.iccids),
            successful=successful,
            failed=failed,
            results=results
        )
        
    except Exception as e:
        logger.error(f"Bulk activation error: {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "message": "Bulk activation failed",
                "error": str(e),
            },
        )


@router.post("/subscriber/sim-serial/{sim_serial}/modify")
def modify_subscriber(
    sim_serial: str,
    payload: ModifySubscriberRequest,
    db: Session = Depends(get_mysql_db),
):
    try:
        # Call Transatel API to modify subscriber
        data = service.modify_subscriber_by_sim_serial(
            db=db,
            sim_serial=sim_serial,
            payload=payload.dict(exclude_none=True),
        )
      
        
        return {
            "success": True,
            "sim_serial": sim_serial,
            "data": data
        }
        
    except Exception as e:
        error_payload = (
            e.args[0] if e.args and isinstance(e.args[0], dict) else str(e)
        )
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "message": "Failed to modify subscriber",
                "error": error_payload,
            },
        )

@router.post("/subscriber/sim-serial/{sim_serial}/suspend")
def suspend_subscriber(
    sim_serial: str,
    payload: SuspendSubscriberRequest,
    db: Session = Depends(get_mysql_db),
):
    try:
        # Call Transatel API to suspend subscriber
        data = service.suspend_subscriber_by_sim_serial(
            db=db,
            sim_serial=sim_serial,
            payload=payload.dict(),
        )
        
        
        return {
            "success": True,
            "sim_serial": sim_serial,
            "data": data
        }
        
    except Exception as e:
        error_payload = (
            e.args[0] if e.args and isinstance(e.args[0], dict) else str(e)
        )
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "message": "Failed to suspend subscriber",
                "error": error_payload,
            },
        )

@router.post("/subscriber/sim-serial/{sim_serial}/reactivate")
def reactivate_subscriber(
    sim_serial: str,
    payload: ReactivateSubscriberRequest,
    db: Session = Depends(get_mysql_db),
):
    try:
        # Call Transatel API to reactivate subscriber
        data = service.reactivate_subscriber_by_sim_serial(
            db=db,
            sim_serial=sim_serial,
            payload=payload.dict(),
        )
 
        return {
            "success": True,
            "sim_serial": sim_serial,
            "data": data
        }
    except Exception as e:
        error_payload = (
            e.args[0] if e.args and isinstance(e.args[0], dict) else str(e)
        )
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "message": "Failed to reactivate subscriber",
                "error": error_payload,
            },
        )
    
@router.post("/subscriber/sim-serial/{sim_serial}/sim-swap")
def sim_swap_subscriber(
    sim_serial: str,
    payload: SimSwapRequest,
    db: Session = Depends(get_mysql_db),
):
    try:
        # Call Transatel API to perform SIM swap
        data = service.sim_swap_by_sim_serial(
            db=db,
            sim_serial=sim_serial,
            payload=payload.dict(),
        )
 
        return {
            "success": True,
            "old_sim_serial": sim_serial,
            "new_sim_serial": payload.newSimSerial,
            "data": data
        }
        
    except Exception as e:
        error_payload = (
            e.args[0] if e.args and isinstance(e.args[0], dict) else str(e)
        )
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "message": "Failed to perform SIM swap",
                "error": error_payload,
            },
        )
    
@router.post("/subscriber/sim-serial/{sim_serial}/terminate")
def terminate_subscriber(
    sim_serial: str,
    payload: TerminateSubscriberRequest,
    db: Session = Depends(get_mysql_db),
):
    try:
        # Call Transatel API to terminate subscriber
        data = service.terminate_subscriber_by_sim_serial(
            db=db,
            sim_serial=sim_serial,
            payload=payload.dict(),
        )

        
        return {
            "success": True,
            "sim_serial": sim_serial,
            "data": data
        }
    except Exception as e:
        error_payload = (
            e.args[0] if e.args and isinstance(e.args[0], dict) else str(e)
        )
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "message": "Failed to terminate subscriber",
                "error": error_payload,
            },
        )

@router.post("/subscriber/sim-serial/{sim_serial}/porting")
def porting_subscriber(
    sim_serial: str,
    payload: PortingSubscriberRequest,
    db: Session = Depends(get_mysql_db),
):
    try:
        # Call Transatel API to port subscriber
        data = service.porting_subscriber(
            db=db,
            sim_serial=sim_serial,
            payload=payload.dict(),
        )
        
        return {
            "success": True,
            "sim_serial": sim_serial,
            "data": data
        }
    except Exception as e:
        error_payload = (
            e.args[0] if e.args and isinstance(e.args[0], dict) else str(e)
        )
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "message": "Failed to port subscriber",
                "error": error_payload,
            },
        )


@router.put("/subscriber/sim-serial/{sim_serial}/contact-info")
def update_subscriber_contact_info(
    sim_serial: str,
    payload: UpdateContactInfoRequest,
    db: Session = Depends(get_mysql_db),
):
    """
    Update subscriber contact info (name, address, email, etc.) via Transatel API.
    
    PUT /subscribers/sim-serial/{sim_serial}/contact-info
    
    Example payload:
    {
        "ratePlan": "M2MA_WW_TSL_PPU_1",
        "subscriberInfo": {
            "pointOfSale": "newPointOfSale",
            "title": "Mr",
            "firstName": "John",
            "lastName": "Doe",
            "dateOfBirth": "1992-12-31",
            "company": "Bread company",
            "address": "rue des pains",
            "zipCode": "75000",
            "city": "PARIS",
            "country": "FRA",
            "contactEmail": "john.doe@example.com"
        }
    }
    """
    try:
        data = service.update_subscriber_contact_info(
            db=db,
            sim_serial=sim_serial,
            payload=payload.dict(exclude_none=True),
        )
        
        return {
            "success": True,
            "sim_serial": sim_serial,
            "message": "Subscriber contact info updated successfully",
            "data": data
        }
        
    except Exception as e:
        error_payload = (
            e.args[0] if e.args and isinstance(e.args[0], dict) else str(e)
        )
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "message": "Failed to update subscriber contact info",
                "error": error_payload,
            },
        )


@router.get("/image/base64")
def get_image_base64():
    try:
        url = (
            "https://api.transatel.com/png;base64,"
            "iVBORw0KGgoAAAANSUhEUgAAAV4AAAFeAQAAAADlUEq3AAACBUlEQVR4Xu2W..."
        )

        data = service.get_png_base64(url)

        return {
            "success": True,
            "data": data
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to fetch image",
                "error": str(e),
            },
        )

# @router.post("/search/lines")
# def search_transatel_lines(
#     page: int = 0,
#     size: int = 200,
#     query: str = "",
#     filters: Optional[List[dict]] = None,
#     db: Session = Depends(get_mysql_db)
# ):
#     """
#     Search lines directly from Transatel API with custom filters
    
#     Uses separate search credentials (TRANSATEL_SEARCH_USERNAME/PASSWORD).
#     Pass filters array to customize search, or pass empty array for all lines.
    
#     Also updates local inventory: if SIM is Active in Transatel but not allocated 
#     in inventory, marks it as pre-activated (isSIMPreActivated = 1).
    
#     Example filters:
#     [{"type":"ValueFilter","fieldName":"group","allowedValues":["Rovers"]}]
#     """
#     try:
#         data = service.search_lines_with_filters(db, page, size, query, filters)
        
#         # Extract pagination info
#         total_count = data.get("totalElements") if isinstance(data, dict) else None
        
#         # Update inventory for active SIMs
#         if isinstance(data, dict) and "content" in data:
#             from models.mysql_models import SimInventory
#             from datetime import datetime
            
#             updated_count = 0
#             for line in data["content"]:
#                 try:
#                     # Check if line is Active, has ICCID, and group is "Rovers"
#                     if (line.get("lineStatus") == "Active" and 
#                         line.get("iccId") and 
#                         line.get("group") == "Rovers"):
                        
#                         iccid = line["iccId"]
                        
#                         # Find SIM in inventory
#                         sim = db.query(SimInventory).filter(
#                             SimInventory.ICCID == iccid
#                         ).first()
                        
#                         if sim:
#                             # Check if SIM is not allocated to any user
#                             if not sim.CustomerID or sim.CustomerID == 0:
#                                 # Mark as pre-activated
#                                 if sim.isSIMPreActivated != 1:
#                                     sim.isSIMPreActivated = 1
#                                     sim.ModifiedOn = datetime.utcnow()
#                                     updated_count += 1
#                                     logger.info(f"Marked SIM {iccid} as pre-activated (Active in Transatel, group=Rovers, not allocated)")
                
#                 except Exception as e:
#                     logger.error(f"Error updating SIM inventory for line: {e}")
#                     continue
            
#             # Commit all updates
#             if updated_count > 0:
#                 db.commit()
#                 logger.info(f"Updated {updated_count} SIMs as pre-activated")
        
#         return {
#             "success": True,
#             "data": data,
#             "total_count": total_count,
#             "page": page,
#             "size": size,
#             "source": "transatel_api",
#             "inventory_updated": updated_count if 'updated_count' in locals() else 0
#         }
#     except Exception as e:
#         error_msg = str(e)
#         raise HTTPException(
#             status_code=400,
#             detail={
#                 "success": False,
#                 "message": "Failed to search lines from Transatel",
#                 "error": error_msg
#             }
#         )


# @router.post("/search/lines-simple")
# def search_transatel_lines_simple(
#     search_request: SimpleSearchRequest,
#     db: Session = Depends(get_mysql_db)
# ):
#     """
#     Search lines with dropdown/enum values (simplified)
    
#     This endpoint provides dropdown options for:
#     - lineStatus: Active, Suspended, Available, Terminated
#     - group: Charity, E2E_TEST_TSL, HIS, HIBS, Rovers
#     - businessEntity: MVNA_UK_EEL_ACQUA_TELECOM
#     - sortField: transatelId, msisdn, iccId, lineStatus, activationDate
#     - sortOrder: ASC, DESC
    
#     Also updates local inventory: if SIM is Active in Transatel but not allocated 
#     in inventory, marks it as pre-activated (isSIMPreActivated = 1).
    
#     Example request body:
#     {
#         "page": 0,
#         "size": 200,
#         "query": "",
#         "filters": {
#             "lineStatus": ["Available"],
#             "group": ["HIS"],
#             "businessEntity": ["MVNA_UK_EEL_ACQUA_TELECOM"]
#         },
#         "sortField": {
#             "fieldName": "transatelId",
#             "sortOrder": "ASC"
#         }
#     }
#     """
#     try:
#         # Convert simplified filters to Transatel API format
#         api_filters = []
        
#         if search_request.filters:
#             if search_request.filters.lineStatus:
#                 api_filters.append({
#                     "type": "ValueFilter",
#                     "fieldName": "lineStatus",
#                     "allowedValues": [status.value for status in search_request.filters.lineStatus]
#                 })
            
#             if search_request.filters.group:
#                 api_filters.append({
#                     "type": "ValueFilter",
#                     "fieldName": "group",
#                     "allowedValues": [group.value for group in search_request.filters.group]
#                 })
            
#             if search_request.filters.businessEntity:
#                 api_filters.append({
#                     "type": "ValueFilter",
#                     "fieldName": "businessEntity",
#                     "allowedValues": [entity.value for entity in search_request.filters.businessEntity]
#                 })
        
#         # Build sort field
#         sort_field = None
#         if search_request.sortField:
#             sort_field = {
#                 "fieldName": search_request.sortField.fieldName.value,
#                 "sortOrder": search_request.sortField.sortOrder.value
#             }
#         else:
#             # Default sort
#             sort_field = {
#                 "fieldName": "transatelId",
#                 "sortOrder": "ASC"
#             }
        
#         # Build complete search request
#         full_search_request = {
#             "query": search_request.query or "",
#             "page": search_request.page,
#             "size": search_request.size,
#             "filters": api_filters,
#             "sortField": sort_field,
#             "aggregationFields": [],
#             "nestedAggregationFields": []
#         }
        
#         # Call the search service
#         data = service.search_lines(db, full_search_request)
        
#         # Extract pagination info
#         total_count = data.get("totalElements") if isinstance(data, dict) else None
        
#         # Update inventory for active SIMs
#         updated_count = 0
#         if isinstance(data, dict) and "content" in data:
#             from models.mysql_models import SimInventory
#             from datetime import datetime
            
#             for line in data["content"]:
#                 try:
#                     # Check if line is Active, has ICCID, and group is "Rovers"
#                     if (line.get("lineStatus") == "Active" and 
#                         line.get("iccId") and 
#                         line.get("group") == "Rovers"):
                        
#                         iccid = line["iccId"]
                        
#                         # Find SIM in inventory
#                         sim = db.query(SimInventory).filter(
#                             SimInventory.ICCID == iccid
#                         ).first()
                        
#                         if sim:
#                             # Check if SIM is not allocated to any user
#                             if not sim.CustomerID or sim.CustomerID == 0:
#                                 # Mark as pre-activated
#                                 if sim.isSIMPreActivated != 1:
#                                     sim.isSIMPreActivated = 1
#                                     sim.ModifiedOn = datetime.utcnow()
#                                     updated_count += 1
#                                     logger.info(f"Marked SIM {iccid} as pre-activated (Active in Transatel, group=Rovers, not allocated)")
                
#                 except Exception as e:
#                     logger.error(f"Error updating SIM inventory for line: {e}")
#                     continue
            
#             # Commit all updates
#             if updated_count > 0:
#                 db.commit()
#                 logger.info(f"Updated {updated_count} SIMs as pre-activated")
        
#         return {
#             "success": True,
#             "data": data,
#             "total_count": total_count,
#             "page": search_request.page,
#             "size": search_request.size,
#             "source": "transatel_api",
#             "filters_applied": api_filters,
#             "sort_applied": sort_field,
#             "inventory_updated": updated_count
#         }
#     except Exception as e:
#         error_msg = str(e)
#         raise HTTPException(
#             status_code=400,
#             detail={
#                 "success": False,
#                 "message": "Failed to search lines from Transatel",
#                 "error": error_msg
#             }
#         )

# @router.get("/search/from-inventory")
# def search_lines_from_inventory(
#     page: int = 0,
#     size: int = 200,
#     status_filter: str = "active",
#     db: Session = Depends(get_mysql_db)
# ):
#     """
#     Search lines from local SIM inventory (no Transatel API call)
    
#     Parameters:
#     - page: Page number (0-indexed)
#     - size: Records per page (max 200)
#     - status_filter: active, allocated, available, or all
    
#     This queries your local simcard_inventory table.
#     Only returns SIMs with CustomerID not null (allocated to customers).
#     """
#     try:
#         from models.mysql_models import SimInventory
        
#         # Build query based on status filter
#         # Always filter for CustomerID not null
#         query = db.query(SimInventory).filter(
#             SimInventory.CustomerID.isnot(None)
#         )
        
#         if status_filter == "active":
#             query = query.filter(
#                 SimInventory.IsInUse == 1,
#                 SimInventory.isTerminate == 0,
#                  SimInventory.CustomerID.isnot(None)
#             )
#         elif status_filter == "allocated":
#             query = query.filter(
#                 SimInventory.IsAllocated == 1,
#                 SimInventory.isTerminate == 0,
#                 SimInventory.CustomerID.isnot(None)
#             )
#         elif status_filter == "available":
#             query = query.filter(
#                 SimInventory.IsAllocated == 0,
#                 SimInventory.IsInUse == 0,
#                 SimInventory.isTerminate == 0
#             )
        
#         # Add ORDER BY for MSSQL pagination (required)
#         query = query.order_by(SimInventory.id.asc())
        
#         # Get total count
#         total_count = query.count()
        
#         # Apply pagination
#         offset = page * size
#         sims = query.offset(offset).limit(size).all()
        
#         # Format response
#         content = []
#         for sim in sims:
#             content.append({
#                 "lineId": sim.id,
#                 "transatelId": sim.ICCID,
#                 "iccId": sim.ICCID,
#                 "msisdn": sim.MSISDN,
#                 "imsi": sim.IMSI,
#                 "lineStatus": "Active" if sim.IsInUse == 1 else "Allocated" if sim.IsAllocated == 1 else "Available",
#                 "activationDate": sim.ActivationDate.isoformat() if sim.ActivationDate else None,
#                 "simFormat": sim.SIMType,
#                 "externalRef": sim.remark,
#                 "customerId": sim.CustomerID,
#                 "isAllocated": sim.IsAllocated,
#                 "isInUse": sim.IsInUse,
#                 "isTerminated": sim.isTerminate,
#                 "allocatedOn": sim.AllocatedOn.isoformat() if sim.AllocatedOn else None,
#                 "simProvider": sim.Simprovider,
#                 "activationCode": sim.ACTIVATIONCODE
#             })
        
#         total_pages = (total_count + size - 1) // size
        
#         return {
#             "success": True,
#             "content": content,
#             "totalElements": total_count,
#             "totalPages": total_pages,
#             "pageNumber": page,
#             "size": size,
#             "offset": offset,
#             "source": "local_inventory",
#             "note": "Only showing SIMs with CustomerID not null"
#         }
        
#     except Exception as e:
#         logger.error(f"Error getting lines from inventory: {e}")
#         raise HTTPException(
#             status_code=500,
#             detail={
#                 "success": False,
#                 "message": "Failed to get lines from inventory",
#                 "error": str(e)
#             }
#         )




@router.post("/import-sims-to-inventory")
def import_sims_to_inventory(
    sim_data: list[dict], 
    providerName: str,
    sim_type: str, 
    db: Session = Depends(get_mysql_db)
):
    """
    Import multiple SIMs to inventory with their details.
    Just checks if ICCID exists and inserts with provided data.
    
    Request body: [
        {"iccid": "89443042334118150980", "msisdn": "447123456789", "activation_code": "LPA:1$..."},
        {"iccid": "89443042334118150981", "msisdn": "447123456790", "activation_code": "LPA:1$..."}
    ]
    Query params: providerName, sim_type
    """
    from datetime import datetime
    from models.mysql_models import SimInventory
    
    try:
        if not sim_data:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": "SIM data array cannot be empty",
                    "error": "No SIM data provided"
                }
            )
        
        if len(sim_data) > 100:  # Limit to prevent abuse
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": "Too many SIMs requested",
                    "error": f"Maximum 100 SIMs allowed, got {len(sim_data)}"
                }
            )
        
        results = []
        errors = []
        imported_count = 0
        skipped_count = 0
        
        logger.info(f"Starting SIM import for {len(sim_data)} SIMs")
        
        for sim_item in sim_data:
            try:
                # Extract data from request
                iccid = sim_item.get("iccid")
                msisdn = sim_item.get("msisdn")
                activation_code = sim_item.get("activation_code")
                
                if not iccid:
                    raise ValueError("ICCID is required for each SIM")
                
                # Check if SIM already exists in inventory
                existing_sim = db.query(SimInventory).filter(
                    SimInventory.iccid == iccid
                ).first()
                
                if existing_sim:
                    logger.info(f"SIM {iccid} already exists in inventory, skipping")
                    results.append({
                        "iccid": iccid,
                        "success": True,
                        "action": "skipped",
                        "message": "SIM already exists in inventory"
                    })
                    skipped_count += 1
                    continue
                
                # Create new SIM inventory record with provided data
                new_sim = SimInventory(
                    sim_number=str(iccid),
                    iccid=str(iccid),
                    msisdn=str(msisdn) if msisdn else None,
                    activation_code=str(activation_code) if activation_code else None,
                    supplier=str(providerName),
                    sim_type=str(sim_type),
                    assigned_to_child_sim_id=None,
                    assigned_at=None,
                    batch_number='AKASHINSWET',
                    status="AVAILABLE"
                )
                
                db.add(new_sim)
                db.flush()  # Flush to catch errors immediately
                imported_count += 1
                
                result_entry = {
                    "iccid": iccid,
                    "success": True,
                    "action": "imported",
                    "data": {
                        "iccid": iccid,
                        "msisdn": msisdn,
                        "activation_code": activation_code[:50] + "..." if activation_code and len(activation_code) > 50 else activation_code,
                        "provider": providerName,
                        "sim_type": sim_type,
                        "status": "AVAILABLE"
                    }
                }
                
                results.append(result_entry)
                logger.info(f"Successfully imported SIM {iccid}")
                
            except Exception as e:
                # Rollback this SIM's changes but continue with others
                db.rollback()
                
                error_payload = str(e)
                error_entry = {
                    "iccid": sim_item.get("iccid", "unknown"),
                    "success": False,
                    "action": "failed",
                    "error": error_payload
                }
                results.append(error_entry)
                errors.append(error_entry)
                logger.error(f"Failed to process SIM {sim_item.get('iccid', 'unknown')}: {error_payload}")
        
        # Commit all changes
        if imported_count > 0:
            db.commit()
            logger.info(f"Successfully imported {imported_count} SIMs to inventory")
        
        return {
            "success": True,
            "message": f"Processed {len(sim_data)} SIMs: {imported_count} imported, {skipped_count} skipped, {len(errors)} failed",
            "total_requested": len(sim_data),
            "imported_count": imported_count,
            "skipped_count": skipped_count,
            "failed_count": len(errors),
            "results": results,
            "errors": errors if errors else None
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions (validation errors)
        raise
    except Exception as e:
        logger.error(f"SIM import failed: {e}")
        try:
            db.rollback()
        except:
            pass
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "SIM import failed",
                "error": str(e)
            }
        )