from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    session_ttl_hours: int = 168
    cookie_secure: bool = False
    cors_origins: str = "http://localhost:3000"
    max_upload_mb: int = 50
    zip_max_depth: int = 3
    zip_max_files: int = 2000
    zip_max_uncompressed_mb: int = 500
    r2_endpoint_url: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    ai_enabled: bool = False

@lru_cache
def get_settings() -> Settings:
    return Settings()
