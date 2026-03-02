from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime
from models.mysql_models import ParentalControl
from models.mysql_models import ChildSimCard, Subscription
from models.mysql_models import PlanMaster, ServiceOption
from schemas.parental_control_schema import ParentalControlSettings, TransatelParam
from services.transatel_service import transatel_service
from utils.logger import logger
import json


class ParentalControlService:
    """Service for managing parental controls"""
    
    def _params_to_dict(self, params: List[Dict[str, str]]) -> Dict[str, str]:
        """Convert list of params to dict for easy lookup"""
        return {p["name"]: p["value"] for p in params}
    
    def _dict_to_params(self, param_dict: Dict[str, str]) -> List[Dict[str, str]]:
        """Convert dict to list of params"""
        return [{"name": k, "value": v} for k, v in param_dict.items()]
    
    def _get_plan_service_options_as_params(self, db: Session, plan_id: int) -> List[Dict[str, str]]:
        """Get service options from plan and convert to Transatel params"""
        try:
            from models.mysql_models import PlanServiceOption
            
            # Get service options for the plan
            service_options = db.query(ServiceOption).join(
                PlanServiceOption,
                ServiceOption.id == PlanServiceOption.service_option_id
            ).filter(
                PlanServiceOption.plan_id == plan_id,
                ServiceOption.is_active == True
            ).all()
            
            params = []
            
            # Convert service options to Transatel params
            for option in service_options:
                # Get the option code (this should match Transatel parameter names)
                # For example: option_code = "BT_VOICE_CALLS_ENABLED"
                param_name = option.option_code
                
                # If option is default enabled, set to "on", otherwise "off"
                value = "on" if option.is_default else "off"
                params.append({"name": param_name, "value": value})
            
            logger.info(f"Loaded {len(params)} service options for plan {plan_id}")
            return params
            
        except Exception as e:
            logger.error(f"Failed to get plan service options: {str(e)}")
            raise
    
    def _map_option_code_to_transatel_param(self, option_code: str) -> Optional[str]:
        """Map service option code to Transatel parameter name"""
        # This method is no longer needed since option_code should directly match Transatel param names
        # But keeping it for backward compatibility
        return option_code
    
    def get_settings(self, db: Session, child_sim_card_id: int, customer_id: int, plan_id: Optional[int] = None) -> Optional[dict]:
        """Get parental control settings in Transatel format"""
        try:
            # Get child SIM card details
            child_sim = db.query(ChildSimCard).filter(
                ChildSimCard.id == child_sim_card_id
            ).first()
            
            if not child_sim:
                return None
            
            # Check if custom settings exist
            control = db.query(ParentalControl).filter(
                ParentalControl.child_sim_card_id == child_sim_card_id
            ).first()
            
            if control and control.custom_settings:
                # Return custom settings
                params = json.loads(control.custom_settings)
                previous_params = json.loads(control.previous_params) if control.previous_params else None
                
                return {
                    "child_sim_card_id": child_sim.id,
                    "child_name": child_sim.child_name,
                    "sim_number": child_sim.sim_number,
                    "iccid": child_sim.iccid,
                    "has_custom_settings": True,
                    "settings_source": "CUSTOM",
                    "params": params,
                    "previous_params": previous_params,
                    "last_synced_at": control.last_synced_at,
                    "created_at": control.created_at,
                    "updated_at": control.updated_at
                }
            
            # No custom settings found - return null/empty
            return {
                "child_sim_card_id": child_sim.id,
                "child_name": child_sim.child_name,
                "sim_number": child_sim.sim_number,
                "iccid": child_sim.iccid,
                "has_custom_settings": False,
                "settings_source": "NOT_SET",
                "params": None,
                "previous_params": None,
                "last_synced_at": None,
                "created_at": None,
                "updated_at": None
            }
            
        except Exception as e:
            logger.error(f"Failed to get parental control settings: {str(e)}")
            raise
    
    def update_settings(self, db: Session, child_sim_card_id: int, customer_id: int, 
                       params: List[Dict[str, str]]) -> ParentalControl:
        """Create or update parental control settings"""
        try:
            # Check if settings exist
            control = db.query(ParentalControl).filter(
                ParentalControl.child_sim_card_id == child_sim_card_id
            ).first()
            
            now = datetime.utcnow()
            params_json = json.dumps(params)
            
            if control:
                # Store old params before updating
                if control.custom_settings:
                    control.previous_params = control.custom_settings
                    logger.info(f"Stored previous params for child SIM {child_sim_card_id}")
                
                # Update with new params
                control.custom_settings = params_json
                control.updated_at = now
            else:
                # Create new (no previous params on first insert)
                control = ParentalControl(
                    child_sim_card_id=child_sim_card_id,
                    customer_id=customer_id,
                    custom_settings=params_json,
                    previous_params=None,  # No previous params on first insert
                    voice_calls_enabled=True,  # Placeholder
                    mobile_data_enabled=True,  # Placeholder
                    sms_enabled=True,  # Placeholder
                    adult_content_filter="MODERATE",  # Placeholder
                    created_at=now,
                    updated_at=now
                )
                db.add(control)
            
            db.commit()
            db.refresh(control)
            logger.info(f"Parental control settings saved for child SIM: {child_sim_card_id}")
            return control
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save parental control settings: {str(e)}")
            raise
    
    def sync_with_transatel(self, db: Session, child_sim_card_id: int, params: List[Dict[str, str]]) -> dict:
        """Sync parental control settings with Transatel"""
        try:
            # Get child SIM details with subscription info
            child_sim = db.query(ChildSimCard).filter(
                ChildSimCard.id == child_sim_card_id
            ).first()
            
            if not child_sim or not child_sim.sim_number:
                logger.error(f"Child SIM not found or missing sim_number: {child_sim_card_id}")
                return {
                    "success": False,
                    "message": "SIM not found or missing sim_number",
                    "error": "SIM not found"
                }
            
            # Get subscription to determine rate plan
            subscription = None
            rate_plan = "MVNA Wholesale PAYM 7"  # Default rate plan
            
            if child_sim.subscription_id:
                from models.mysql_models import Subscription, PlanMaster
                subscription = db.query(Subscription).filter(
                    Subscription.id == child_sim.subscription_id
                ).first()
                
                if subscription and subscription.plan_id:
                    plan = db.query(PlanMaster).filter(
                        PlanMaster.id == subscription.plan_id
                    ).first()
                    
                    # Use plan's rate plan if available, otherwise use default
                    if plan and hasattr(plan, 'transatel_rate_plan') and plan.transatel_rate_plan:
                        rate_plan = plan.transatel_rate_plan
            
            logger.info(f"Syncing parental controls for SIM {child_sim.sim_number} with rate plan: {rate_plan}")
            
            # Build payload with rate plan and options
            payload = {
                "ratePlan": rate_plan,
                "options": params
            }
            
            logger.info(f"Transatel modify payload: {payload}")
            
            # Call Transatel API
            result = transatel_service.modify_subscriber_by_sim_serial(
                db=db,
                sim_serial=child_sim.sim_number,
                payload=payload
            )
            if result:
                # Update last synced timestamp
                control = db.query(ParentalControl).filter(
                    ParentalControl.child_sim_card_id == child_sim_card_id
                ).first()
                
                if control:
                    control.last_synced_at = datetime.utcnow()
                    db.commit()
                
                logger.info(f"Successfully synced parental controls with Transatel for SIM: {child_sim.sim_number}")
                return {
                    "success": True,
                    "message": "Synced successfully",
                    "rate_plan": rate_plan,
                    "params_sent": params
                }
            else:
                # logger.error(f"Failed to sync with Transatel: {result.get('error')}")
                return {
                    "success": False,
                    "message": "Failed to sync with Transatel",
                    # "error": result.get("error", "Unknown error"),
                    "params_sent": params
                }
            
        except Exception as e:
            logger.error(f"Failed to sync with Transatel: {str(e)}")
            return {
                "success": False,
                "message": "Exception occurred during sync",
                "error": str(e)
            }
    
    def get_all_for_customer(self, db: Session, customer_id: int) -> List[dict]:
        """Get all parental control settings for a customer's children"""
        try:
            # Get all child SIM cards for customer's subscriber
            from models.mysql_models import Subscriber
            
            subscriber = db.query(Subscriber).filter(
                Subscriber.customer_id == customer_id
            ).first()
            
            if not subscriber:
                return []
            
            child_sims = db.query(ChildSimCard).filter(
                ChildSimCard.subscriber_id == subscriber.id
            ).all()
            
            results = []
            for child_sim in child_sims:
                settings = self.get_settings(db, child_sim.id, customer_id)
                if settings:
                    results.append(settings)
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get customer parental controls: {str(e)}")
            raise


parental_control_service = ParentalControlService()
