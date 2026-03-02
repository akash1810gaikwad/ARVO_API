from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models.mysql_models import TransatelToken,TransatelAPILog

def get_valid_token(db: Session):
    return (
        db.query(TransatelToken)
        .filter(TransatelToken.expires_at > datetime.utcnow())
        .order_by(TransatelToken.id.desc())
        .first()
    )

def save_token(db: Session, access_token: str, token_type: str, expires_in: int):
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    token = TransatelToken(
        access_token=access_token,
        token_type=token_type,
        expires_at=expires_at
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token

def clear_tokens(db: Session):
    """Clear all Transatel tokens from database"""
    db.query(TransatelToken).delete()
    db.commit()

# app/repositories/transatel_log_repo.py



def log_transatel_api(
    db: Session,
    *,
    api_name: str,
    endpoint: str,
    request_payload: dict | None,
    response_payload: dict | None,
    status: str,
    http_status_code: int | None = None,
    error_message: str | None = None,
):
    import json
    
    # Convert dicts to JSON strings
    request_json = json.dumps(request_payload) if request_payload else None
    response_json = json.dumps(response_payload) if response_payload else None
    
    log = TransatelAPILog(
        api_name=api_name,
        endpoint=endpoint,
        request_payload=request_json,
        response_payload=response_json,
        status=status,
        http_status_code=http_status_code,
        error_message=error_message,
    )
    db.add(log)
    db.commit()
