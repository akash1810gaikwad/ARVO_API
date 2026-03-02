from pydantic_settings import BaseSettings
from urllib.parse import quote_plus
from pydantic import validator, Field

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "MyApp"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    
    # MongoDB
    MONGODB_URL: str
    MONGODB_DB_NAME: str
    
    
    # MySQL
    MYSQL_ENABLED: bool = True
    MYSQL_HOST: str = ""
    MYSQL_PORT: int = 3306
    MYSQL_USERNAME: str = ""
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = ""
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE_PATH: str = "logs/app.log"

    # Transatel API Configuration
    TRANSATEL_BASE_URL: str = "https://api.transatel.com"
    TRANSATEL_USERNAME: str = ""
    TRANSATEL_PASSWORD: str = ""
    
    # Transatel Search API Configuration (separate credentials for search only)
    TRANSATEL_SEARCH_USERNAME: str = ""
    TRANSATEL_SEARCH_PASSWORD: str = ""
    
    # Transatel Development Mode (use mock data when True)
    TRANSATEL_DEV_MODE: bool = False
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"
    
    # Cron Jobs
    ENABLE_CRON_JOBS: bool = True
    
    # JWT Configuration
    SECRET_KEY: str = "your-secret-key-change-in-production-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    
    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    
    # Stripe Payment
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    
    # Whop Payment Gateway
    WHOP_API_KEY: str = ""
    WHOP_WEBHOOK_SECRET: str = ""
    
    @property
    def cors_origins_list(self):
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    @property
    def mysql_connection_url(self) -> str:
        """Generate MySQL connection URL using pymysql"""
        if not self.MYSQL_HOST or not self.MYSQL_DATABASE:
            return ""
        
        return (
            f"mysql+pymysql://{self.MYSQL_USERNAME}:"
            f"{quote_plus(self.MYSQL_PASSWORD)}@"
            f"{self.MYSQL_HOST}:{self.MYSQL_PORT}/"
            f"{self.MYSQL_DATABASE}?charset=utf8mb4"
        )
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env file


settings = Settings()
