"""
Application configuration and environment variables
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "mealplan"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Database (MongoDB)
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "shopify_meals_db"
    
    # Shopify
    SHOPIFY_SHOP_DOMAIN: str
    SHOPIFY_API_KEY: str
    SHOPIFY_API_SECRET: str
    SHOPIFY_APP_PROXY_SECRET: str  # Shared secret for app proxy validation
    SHOPIFY_STOREFRONT_ACCESS_TOKEN: Optional[str] = None  # Storefront API access token
    SHOPIFY_ADMIN_ACCESS_TOKEN: Optional[str] = None  # Admin API access token (fallback if OAuth token not available)
    
    # Subscription Providers (Optional)
    RECHARGE_API_KEY: Optional[str] = None  # Recharge API key if using Recharge
    RECHARGE_SHOP: Optional[str] = None  # Recharge shop identifier
    APPSTLE_API_KEY: Optional[str] = None  # Appstle API key if using Appstle
    LOOP_API_KEY: Optional[str] = None  # Loop API key if using Loop
    
    # Security
    SECRET_KEY: str  # For JWT tokens
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Admin
    ADMIN_API_KEY: Optional[str] = None
    
    # PDF Storage
    PDF_STORAGE_PATH: str = "./storage/pdfs"
    PDF_BASE_URL: str = "https://api.yourdomain.com/pdfs"
    PDF_GENERATION_METHOD: str = "reportlab"  # Options: reportlab, pdfmonkey, documint
    
    # External PDF Services (Optional)
    PDFMONKEY_API_KEY: Optional[str] = None
    PDFMONKEY_TEMPLATE_ID: Optional[str] = None
    DOCUMINT_API_KEY: Optional[str] = None
    
    # OpenAI (Optional)
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-3.5-turbo"
    
    # App Base URL (for OAuth redirects)
    APP_BASE_URL: str = "http://localhost:8000"  # Update with ngrok URL in production
    
    # CORS
    ALLOWED_ORIGINS: str = "https://*.myshopify.com"
    
    @property
    def allowed_origins_list(self) -> list[str]:
        """Parse ALLOWED_ORIGINS from comma-separated string"""
        if isinstance(self.ALLOWED_ORIGINS, list):
            return self.ALLOWED_ORIGINS
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

