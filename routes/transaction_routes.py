from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
import logging

from config.mysql_database import get_mysql_db
from models.mysql_models import Payment, Subscriber, Customer
from models.mysql_models import Order
from middleware.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/transactions", tags=["Transactions"])


@router.get("/{customer_id}")
def get_customer_transactions(
    customer_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Records per page"),
    db: Session = Depends(get_mysql_db),
    current_user: Customer = Depends(get_current_user)
):
    """Get transaction history for a customer"""
    try:
        # Get subscriber for this customer
        subscriber = db.query(Subscriber).filter(Subscriber.customer_id == customer_id).first()
        
        if not subscriber:
            return {
                "transactions": [],
                "total": 0,
                "page": page,
                "limit": limit,
                "has_next": False,
                "has_previous": False
            }
        
        # Calculate offset
        offset = (page - 1) * limit
        
        # Use raw SQL to properly handle datetimeoffset
        from sqlalchemy import text
        
        count_query = text("""
            SELECT COUNT(*) as total
            FROM payments
            WHERE subscriber_id = :subscriber_id
        """)
        
        total_result = db.execute(count_query, {"subscriber_id": subscriber.id}).fetchone()
        total = total_result[0] if total_result else 0
        
        # Get payments with proper datetime conversion (MySQL syntax)
        query = text("""
            SELECT 
                p.id,
                p.subscriber_id,
                p.stripe_payment_intent_id,
                p.stripe_invoice_id,
                p.payment_type,
                p.amount,
                p.currency,
                p.status,
                p.payment_method_type,
                p.failure_reason,
                DATE_FORMAT(p.payment_date, '%Y-%m-%dT%H:%i:%s') as payment_date,
                DATE_FORMAT(p.created_at, '%Y-%m-%dT%H:%i:%s') as created_at,
                DATE_FORMAT(p.updated_at, '%Y-%m-%dT%H:%i:%s') as updated_at,
                p.order_id
            FROM payments p
            WHERE p.subscriber_id = :subscriber_id
            ORDER BY p.id DESC
            LIMIT :limit OFFSET :offset
        """)
        
        results = db.execute(query, {
            "subscriber_id": subscriber.id,
            "offset": offset,
            "limit": limit
        }).fetchall()
        
        # Build transactions list
        transactions = []
        for row in results:
            # Determine transaction type
            transaction_type = "SUBSCRIPTION"
            description = "Subscription payment"
            
            if row.payment_type:
                if "INITIAL" in row.payment_type.upper():
                    transaction_type = "SUBSCRIPTION"
                    description = "Initial subscription payment"
                elif "RENEWAL" in row.payment_type.upper():
                    transaction_type = "RENEWAL"
                    description = "Subscription renewal"
                elif "TOPUP" in row.payment_type.upper():
                    transaction_type = "TOPUP"
                    description = "Account top-up"
            
            transactions.append({
                "id": row.id,
                "customer_id": customer_id,
                "subscriber_id": row.subscriber_id,
                "stripe_session_id": None,
                "stripe_payment_intent_id": row.stripe_payment_intent_id,
                "stripe_invoice_id": row.stripe_invoice_id,
                "transaction_type": transaction_type,
                "amount": str(row.amount) if row.amount else "0.00",
                "currency": row.currency or "EUR",
                "status": row.status.lower() if row.status else "pending",
                "payment_method": row.payment_method_type or "card",
                "description": description,
                "failure_reason": row.failure_reason,
                "processed_at": row.payment_date or row.created_at,
                "created_at": row.created_at,
                "updated_at": row.updated_at
            })
        
        # Calculate pagination
        has_next = (page * limit) < total
        has_previous = page > 1
        
        return {
            "transactions": transactions,
            "total": total,
            "page": page,
            "limit": limit,
            "has_next": has_next,
            "has_previous": has_previous
        }
        
    except Exception as e:
        logger.error(f"Error fetching transactions for customer {customer_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch transactions: {str(e)}"
        )
