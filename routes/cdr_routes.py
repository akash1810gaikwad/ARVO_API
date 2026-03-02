from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List
from datetime import datetime, date
import logging

from config.mysql_database import get_mysql_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/cdr", tags=["CDR"])


@router.get("/data")
def get_data_cdrs(
    from_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    to_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    msisdn: Optional[str] = Query(None, description="Filter by MSISDN"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(100, ge=1, le=1000, description="Records per page"),
    db: Session = Depends(get_mysql_db)
):
    """
    Get data CDRs (Call Detail Records) for a date range.
    Only returns CDRs where cdr_type = 'data'.
    """
    try:
        # Build the WHERE clause
        where_conditions = ["cdr_type = 'data'"]
        params = {
            "from_date": from_date.strftime("%Y-%m-%d"),
            "to_date": to_date.strftime("%Y-%m-%d")
        }
        
        # Add date range filter - using EventTime as the primary timestamp for data CDRs
        where_conditions.append("DATE(EventTime) BETWEEN :from_date AND :to_date")
        
        # Add MSISDN filter if provided
        if msisdn:
            where_conditions.append("MSISDN = :msisdn")
            params["msisdn"] = msisdn
        
        where_clause = " AND ".join(where_conditions)
        
        # Count total records
        count_query = f"""
            SELECT COUNT(*) as total
            FROM cdr_records
            WHERE {where_clause}
        """
        
        count_result = db.execute(text(count_query), params).fetchone()
        total_records = count_result[0] if count_result else 0
        
        # Calculate pagination
        offset = (page - 1) * page_size
        total_pages = (total_records + page_size - 1) // page_size
        
        # Fetch CDR records
        query = f"""
            SELECT 
                id,
                file_id,
                row_num,
                cdr_type,
                ingested_at_utc,
                RecordId,
                MSISDN,
                IMSI,
                SubscriberId,
                COS,
                MVNO,
                CallType,
                Bearer,
                Anumber,
                Bnumber,
                Rnumber,
                Prefix,
                Destination,
                LocationZoneName,
                LocationCode,
                ISO3,
                MCC,
                MNC,
                CellId,
                SetupTime,
                AnswerTime,
                DisconnectTime,
                Duration,
                APN,
                RAT,
                IMEI,
                EventTime,
                USU,
                MMSSize,
                MMSType,
                Charge,
                TariffClass,
                VAT
            FROM cdr_records
            WHERE {where_clause}
            ORDER BY EventTime DESC
            LIMIT :limit OFFSET :offset
        """
        
        params["limit"] = page_size
        params["offset"] = offset
        
        result = db.execute(text(query), params)
        records = result.fetchall()
        
        # Convert to list of dicts
        cdr_list = []
        for record in records:
            cdr_dict = {
                "id": record[0],
                "file_id": record[1],
                "row_num": record[2],
                "cdr_type": record[3],
                "ingested_at_utc": record[4].isoformat() if record[4] else None,
                "RecordId": record[5],
                "MSISDN": record[6],
                "IMSI": record[7],
                "SubscriberId": record[8],
                "COS": record[9],
                "MVNO": record[10],
                "CallType": record[11],
                "Bearer": record[12],
                "Anumber": record[13],
                "Bnumber": record[14],
                "Rnumber": record[15],
                "Prefix": record[16],
                "Destination": record[17],
                "LocationZoneName": record[18],
                "LocationCode": record[19],
                "ISO3": record[20],
                "MCC": record[21],
                "MNC": record[22],
                "CellId": record[23],
                "SetupTime": record[24],
                "AnswerTime": record[25],
                "DisconnectTime": record[26],
                "Duration": record[27],
                "APN": record[28],
                "RAT": record[29],
                "IMEI": record[30],
                "EventTime": record[31],
                "USU": record[32],
                "MMSSize": record[33],
                "MMSType": record[34],
                "Charge": record[35],
                "TariffClass": record[36],
                "VAT": record[37]
            }
            cdr_list.append(cdr_dict)
        
        return {
            "success": True,
            "data": cdr_list,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_records": total_records,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            },
            "filters": {
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
                "msisdn": msisdn,
                "cdr_type": "data"
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching data CDRs: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to fetch data CDRs",
                "error": str(e)
            }
        )
