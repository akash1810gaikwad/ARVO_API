import requests
import logging
from typing import Dict, Any, Optional,List
from sqlalchemy.orm import Session

from repositories.transatel_token_repo import get_valid_token, save_token, log_transatel_api
from config.settings import settings

logger = logging.getLogger(__name__)

# Constants
class Messages:
    TRANSATEL_TIMEOUT = "Transatel API request timed out"
    TRANSATEL_AUTH_FAILED = "Transatel authentication failed"

class StatusCodes:
    UNAUTHORIZED = 401

class Endpoints:
    TRANSATEL_AUTH = "/authentication/api/token"

class TransatelService:
    """
    Centralized Transatel Service with improved configuration and error handling
    - Handles token management
    - Makes API calls with automatic retry
    - Logs request + response automatically
    - Uses environment-based configuration
    """

    def __init__(self):
        self.base_url = settings.TRANSATEL_BASE_URL
        self.username = settings.TRANSATEL_USERNAME
        self.password = settings.TRANSATEL_PASSWORD
        
        # Separate credentials for search API
        self.search_username = settings.TRANSATEL_SEARCH_USERNAME or self.username
        self.search_password = settings.TRANSATEL_SEARCH_PASSWORD or self.password
        
        self.timeout = 15  # Reduced timeout for faster failure
        
        # Development mode - use mock data if enabled
        self.dev_mode = settings.TRANSATEL_DEV_MODE
        
        self.is_configured = bool(self.username and self.password)
        
        if self.dev_mode:
            logger.warning("⚠️  TRANSATEL DEVELOPMENT MODE ENABLED - Using mock data instead of real API")
        elif not self.is_configured:
            logger.warning("Transatel credentials not configured - Transatel features will be disabled")

    def _check_configuration(self):
        """Check if Transatel is properly configured"""
        if not self.is_configured:
            raise ValueError("Transatel credentials must be set in environment variables")

    # ------------------------------------------------------------------
    # AUTH
    # ------------------------------------------------------------------

    def login(self, db: Session, scope: Optional[str] = None) -> str:
        """Authenticate with Transatel API using OAuth2 client credentials
        
        Args:
            db: Database session
            scope: Optional OAuth2 scope (e.g., "search" for search API access)
        """
        self._check_configuration()
        
        url = f"{self.base_url}{Endpoints.TRANSATEL_AUTH}"
        
        try:
            # Build authentication data as string (not dict)
            auth_data = "grant_type=client_credentials"
            
            # Add scope if provided (for search API or other specific scopes)
            if scope:
                auth_data += f"&scope={scope}"
                logger.info(f"Requesting token with scope: {scope}")
            
            logger.info(f"Attempting Transatel authentication to: {url}")
            logger.info(f"Using username: {self.username}")
            
            # Create Basic Auth header manually
            import base64
            auth_string = f"{self.username}:{self.password}"
            auth_bytes = auth_string.encode('ascii')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
            
            response = requests.post(
                url,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {auth_b64}"
                },
                data=auth_data,
                timeout=self.timeout,
            )
            
            # Log response details for debugging
            logger.info(f"Response status code: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"Authentication failed with status {response.status_code}")
                logger.error(f"Response body: {response.text}")
                
                # Try to parse error response
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error_description') or error_data.get('detail') or response.text
                except:
                    error_msg = response.text
                
                raise Exception(f"Authentication failed (HTTP {response.status_code}): {error_msg}")
            
            response.raise_for_status()

            data = response.json()
            
            # Save token to database
            save_token(
                db=db,
                access_token=data["access_token"],
                token_type=data.get("token_type", "Bearer"),
                expires_in=data["expires_in"],
            )
            
            logger.info(f"Transatel authentication successful{' with scope: ' + scope if scope else ''}")
            return data["access_token"]
            
        except requests.exceptions.Timeout:
            logger.error("Transatel authentication timeout")
            raise Exception(Messages.TRANSATEL_TIMEOUT)
        except requests.exceptions.RequestException as e:
            logger.error(f"Transatel authentication failed: {e}")
            logger.error(f"Request URL: {url}")
            logger.error(f"Username: {self.username}")
            raise Exception(f"{Messages.TRANSATEL_AUTH_FAILED}: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during Transatel authentication: {e}")
            raise

    def get_access_token(self, db: Session) -> str:
        """Get valid access token, refresh if needed"""
        if self.dev_mode:
            logger.info("[DEV MODE] Returning mock access token")
            return "mock_dev_token_12345"
        
        self._check_configuration()
        
        try:
            token = get_valid_token(db)
            if token:
                return token.access_token
            
            logger.info("No valid token found, authenticating...")
            return self.login(db)
            
        except Exception as e:
            logger.error(f"Error getting access token: {e}")
            raise

    def _auth_headers(self, db: Session) -> Dict[str, str]:
        """Get authentication headers with valid token"""
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.get_access_token(db)}",
        }

    # ------------------------------------------------------------------
    # CORE REQUEST HANDLER (AUTO LOGGING)
    # ------------------------------------------------------------------

    def _request(
        self,
        *,
        db: Session,
        method: str,
        endpoint: str,
        api_name: str,
        headers: Optional[Dict[str, str]] = None,
        payload: Optional[dict] = None,
        success_codes: tuple = (200, 201),
        retry_count: int = 1,
    ) -> Dict[str, Any]:
        """
        Core request handler with automatic logging and retry logic
        """
        url = f"{self.base_url}{endpoint}"
        
        # Use auth headers if none provided
        if headers is None:
            headers = self._auth_headers(db)
        
        last_exception = None
        last_response_data = None
        
        for attempt in range(retry_count + 1):
            try:
                logger.debug(f"Making {method} request to {url} (attempt {attempt + 1})")
                
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
                
                # Try to parse response JSON
                try:
                    response_data = response.json() if response.content else None
                except:
                    response_data = {"raw_response": response.text}
                
                last_response_data = response_data
                
                # Log the API call
                log_transatel_api(
                    db=db,
                    api_name=api_name,
                    endpoint=endpoint,
                    request_payload=payload,
                    response_payload=response_data,
                    status="SUCCESS" if response.status_code in success_codes else "FAILED",
                    http_status_code=response.status_code,
                    error_message=None if response.status_code in success_codes else response.text,
                )
                
                if response.status_code in success_codes:
                    logger.info(f"Transatel API call successful: {api_name}")
                    return response_data
                
                # Handle authentication errors - force token refresh
                if response.status_code == StatusCodes.UNAUTHORIZED:
                    logger.warning(f"401 Unauthorized on attempt {attempt + 1}, forcing token refresh...")
                    
                    # Clear expired tokens and force new login
                    from repositories.transatel_token_repo import clear_tokens
                    clear_tokens(db)
                    
                    # Get fresh token
                    try:
                        new_token = self.login(db)
                        headers = {
                            "Accept": "application/json",
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {new_token}",
                        }
                        logger.info("Token refreshed successfully, retrying request...")
                        continue
                    except Exception as login_error:
                        logger.error(f"Failed to refresh token: {login_error}")
                        raise Exception(f"Authentication failed: {str(login_error)}")
                
                # Handle other errors
                error_msg = f"API call failed with status {response.status_code}: {response.text}"
                logger.error(error_msg)
                
                # Raise with response data for better error messages
                error_dict = {
                    "status_code": response.status_code,
                    "message": error_msg,
                    "response": response_data
                }
                raise Exception(error_dict)
                
            except requests.exceptions.Timeout as e:
                last_exception = e
                logger.warning(f"Request timeout (attempt {attempt + 1}): {e}")
                if attempt == retry_count:
                    break
                    
            except requests.exceptions.RequestException as e:
                last_exception = e
                logger.error(f"Request failed (attempt {attempt + 1}): {e}")
                if attempt == retry_count:
                    break
                    
            except Exception as e:
                # If it's our custom error dict, re-raise it
                if isinstance(e.args[0] if e.args else None, dict):
                    last_exception = e
                    break
                last_exception = e
                logger.error(f"Unexpected error (attempt {attempt + 1}): {e}")
                if attempt == retry_count:
                    break
        
        # Log failed request
        log_transatel_api(
            db=db,
            api_name=api_name,
            endpoint=endpoint,
            request_payload=payload,
            response_payload=last_response_data,
            status="FAILED",
            http_status_code=None,
            error_message=str(last_exception),
        )
        
        raise last_exception or Exception("Request failed after all retries")

    # ------------------------------------------------------------------
    # ESIM OPERATIONS
    # ------------------------------------------------------------------

    def get_esim_by_sim_serial(self, db: Session, sim_serial: str) -> Dict[str, Any]:
        """Get eSIM details by SIM serial number"""
        if self.dev_mode:
            logger.info(f"[DEV MODE] Returning mock eSIM for SIM: {sim_serial}")
            return {
                "sim_serial": sim_serial,
                "sim_type": "eSIM",
                "lpa_code": f"LPA:1$sm-v4-010-a-gtm.pr.go-esim.com${sim_serial[-16:]}",
                "qr_code_url": f"https://mock-qr-code.example.com/{sim_serial}.png",
                "status": "READY",
                "profile_status": "AVAILABLE",
                "_mock": True
            }
        
        endpoint = f"/sim-management/sims/api/esims/sim-serial/{sim_serial}"
        return self._request(
            db=db,
            method="GET",
            endpoint=endpoint,
            api_name="get_esim_by_sim_serial",
        )

    # ------------------------------------------------------------------
    # SUBSCRIBER OPERATIONS
    # ------------------------------------------------------------------

    def get_subscriber_by_sim_serial(self, db: Session, sim_serial: str) -> Dict[str, Any]:
        """Get subscriber by SIM serial number"""
        endpoint = f"/connectivity-management/subscribers/api/subscribers/sim-serial/{sim_serial}"
        return self._request(
            db=db,
            method="GET",
            endpoint=endpoint,
            api_name="get_subscriber_by_sim_serial",
        )

    def get_subscriber_by_msisdn(self, db: Session, msisdn: str) -> Dict[str, Any]:
        """Get subscriber by MSISDN"""
        endpoint = f"/connectivity-management/subscribers/api/subscribers/msisdn/{msisdn}"
        return self._request(
            db=db,
            method="GET",
            endpoint=endpoint,
            api_name="get_subscriber_by_msisdn",
        )

    def activate_subscriber(self, db: Session, sim_serial: str, payload: dict) -> Dict[str, Any]:
        endpoint = f"/connectivity-management/subscribers/api/subscribers/sim-serial/{sim_serial}/activate"
        return self._request(
            db=db,
            method="POST",
            endpoint=endpoint,
            api_name="activate_subscriber",
            payload=payload,
            success_codes=(200, 201, 202),
        )

    def modify_subscriber(self, db: Session, sim_serial: str, payload: dict) -> Dict[str, Any]:
        """Modify subscriber"""
        endpoint = f"/connectivity-management/subscribers/api/subscribers/sim-serial/{sim_serial}/modify"
        return self._request(
            db=db,
            method="POST",
            endpoint=endpoint,
            api_name="modify_subscriber",
            payload=payload,
        )

    def suspend_subscriber(self, db: Session, sim_serial: str, payload: dict) -> Dict[str, Any]:
        """Suspend subscriber"""
        endpoint = f"/connectivity-management/subscribers/api/subscribers/sim-serial/{sim_serial}/suspend"
        return self._request(
            db=db,
            method="POST",
            endpoint=endpoint,
            api_name="suspend_subscriber",
            payload=payload,
        )

    def reactivate_subscriber(self, db: Session, sim_serial: str, payload: dict) -> Dict[str, Any]:
        """Reactivate subscriber"""
        endpoint = f"/connectivity-management/subscribers/api/subscribers/sim-serial/{sim_serial}/reactivate"
        return self._request(
            db=db,
            method="POST",
            endpoint=endpoint,
            api_name="reactivate_subscriber",
            payload=payload,
        )

    def sim_swap(self, db: Session, sim_serial: str, payload: dict) -> Dict[str, Any]:
        """Perform SIM swap"""
        endpoint = f"/connectivity-management/subscribers/api/subscribers/sim-serial/{sim_serial}/sim-swap"
        return self._request(
            db=db,
            method="POST",
            endpoint=endpoint,
            api_name="sim_swap",
            payload=payload,
        )

    def terminate_subscriber(self, db: Session, sim_serial: str, payload: dict) -> Dict[str, Any]:
        """Terminate subscriber"""
        endpoint = f"/connectivity-management/subscribers/api/subscribers/sim-serial/{sim_serial}/terminate"
        return self._request(
            db=db,
            method="POST",
            endpoint=endpoint,
            api_name="terminate_subscriber",
            payload=payload,
        )
    
    def porting_subscriber(self, db: Session, sim_serial: str, payload: dict) -> Dict[str, Any]:
        """porting subscriber"""
        endpoint = f"/connectivity-management/subscribers/api/portability/uk/sim-serial/{sim_serial}/request"
        return self._request(
            db=db,
            method="POST",
            endpoint=endpoint,
            api_name="porting_subscriber",
            payload=payload,
        )

    def update_subscriber_contact_info(self, db: Session, sim_serial: str, payload: dict) -> Dict[str, Any]:
        """Update subscriber contact info (name, address, email, etc.)"""
        endpoint = f"/connectivity-management/subscribers/api/subscribers/sim-serial/{sim_serial}/contact-info"
        return self._request(
            db=db,
            method="PUT",
            endpoint=endpoint,
            api_name="update_subscriber_contact_info",
            payload=payload,
            success_codes=(200, 201, 204),
        )



    # ------------------------------------------------------------------
    # UTILITY METHODS
    # ------------------------------------------------------------------

    def get_image_base64(self, db: Session, image_url: str) -> Dict[str, Any]:
        """Fetch image and return as base64"""
        try:
            response = requests.get(image_url, timeout=self.timeout)
            response.raise_for_status()
            
            import base64
            encoded_image = base64.b64encode(response.content).decode('utf-8')
            
            return {
                "success": True,
                "data": {
                    "base64": encoded_image,
                    "content_type": response.headers.get('content-type', 'image/png')
                }
            }
            
        except Exception as e:
            logger.error(f"Error fetching image: {e}")
            raise Exception(f"Failed to fetch image: {str(e)}")

    def get_png_base64(self, image_url: str) -> str:
        """Fetch PNG image and return as base64 string"""
        try:
            response = requests.get(image_url, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Error fetching PNG base64: {e}")
            raise Exception(f"Failed to fetch PNG: {str(e)}")

    def health_check(self, db: Session) -> Dict[str, Any]:
        """Check Transatel API health"""
        try:
            # Try to get a valid token
            token = self.get_access_token(db)
            return {
                "transatel_api": "healthy",
                "authenticated": bool(token),
                "base_url": self.base_url
            }
        except Exception as e:
            logger.error(f"Transatel health check failed: {e}")
            return {
                "transatel_api": "unhealthy",
                "authenticated": False,
                "error": str(e),
                "base_url": self.base_url
            }

    # ------------------------------------------------------------------
    # BACKWARD COMPATIBILITY METHODS (for existing routes)
    # ------------------------------------------------------------------

    def activate_subscriber_by_sim_serial(self, db: Session, sim_serial: str, payload: dict) -> Dict[str, Any]:
        """Activate subscriber by SIM serial (backward compatibility)"""
        return self.activate_subscriber(db, sim_serial, payload)

    def modify_subscriber_by_sim_serial(self, db: Session, sim_serial: str, payload: dict) -> Dict[str, Any]:
        """Modify subscriber by SIM serial (backward compatibility)"""
        return self.modify_subscriber(db, sim_serial, payload)

    def suspend_subscriber_by_sim_serial(self, db: Session, sim_serial: str, payload: dict) -> Dict[str, Any]:
        """Suspend subscriber by SIM serial (backward compatibility)"""
        return self.suspend_subscriber(db, sim_serial, payload)

    def reactivate_subscriber_by_sim_serial(self, db: Session, sim_serial: str, payload: dict) -> Dict[str, Any]:
        """Reactivate subscriber by SIM serial (backward compatibility)"""
        return self.reactivate_subscriber(db, sim_serial, payload)

    def sim_swap_by_sim_serial(self, db: Session, sim_serial: str, payload: dict) -> Dict[str, Any]:
        """SIM swap by SIM serial (backward compatibility)"""
        return self.sim_swap(db, sim_serial, payload)

    def terminate_subscriber_by_sim_serial(self, db: Session, sim_serial: str, payload: dict) -> Dict[str, Any]:
        """Terminate subscriber by SIM serial (backward compatibility)"""
        return self.terminate_subscriber(db, sim_serial, payload)

    # ------------------------------------------------------------------
    # SEARCH API METHODS (Uses separate search credentials)
    # ------------------------------------------------------------------

    def _get_search_token(self, db: Session) -> str:
        """Get access token using search credentials"""
        url = f"{self.base_url}/authentication/api/token"
        
        try:
            # Create Basic Auth header manually
            import base64
            auth_string = f"{self.search_username}:{self.search_password}"
            auth_bytes = auth_string.encode('ascii')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
            
            response = requests.post(
                url,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {auth_b64}"
                },
                data="grant_type=client_credentials",
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            logger.info("Transatel search authentication successful")
            return data["access_token"]
        except Exception as e:
            logger.error(f"Search authentication failed: {e}")
            raise Exception(f"Search API authentication failed: {str(e)}")

    def search_lines(self, db: Session, search_request: dict) -> Dict[str, Any]:
        """Search lines using Transatel search API with search credentials
        
        Note: This uses separate search credentials (TRANSATEL_SEARCH_USERNAME/PASSWORD)
        """
        endpoint = "/search/api/v2/search/lines"
        
        # Build query parameters
        query_params = {
            "query": search_request.get("query", ""),
            "page": search_request.get("page", 0),
            "size": search_request.get("size", 200)
        }
        
        # Build the request payload
        payload = {
            "filters": search_request.get("filters", []),
            "sortField": search_request.get("sortField", {
                "fieldName": "transatelId",
                "sortOrder": "ASC"
            }),
            "aggregationFields": search_request.get("aggregationFields", []),
            "nestedAggregationFields": search_request.get("nestedAggregationFields", [])
        }
        
        # Build the full URL with query parameters
        query_string = "&".join([f"{k}={v}" for k, v in query_params.items()])
        full_endpoint = f"{endpoint}?{query_string}"
        
        try:
            # Get search token
            search_token = self._get_search_token(db)
            
            # Use search credentials
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {search_token}",
            }
            
            return self._request(
                db=db,
                method="POST",
                endpoint=full_endpoint,
                api_name="search_lines",
                payload=payload,
                headers=headers,
                success_codes=(200, 201)
            )
        except Exception as e:
            logger.error(f"Search API error: {e}")
            raise

    def search_lines_with_filters(
        self, 
        db: Session, 
        page: int = 0, 
        size: int = 200, 
        query: str = "",
        filters: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Search lines with custom filters using search credentials"""
        search_request = {
            "query": query,
            "page": page,
            "size": size,
            "filters": filters or [],
            "sortField": {
                "fieldName": "transatelId",
                "sortOrder": "ASC"
            },
            "aggregationFields": [],
            "nestedAggregationFields": []
        }
        
        return self.search_lines(db, search_request)


# Create singleton instance
transatel_service = TransatelService()
