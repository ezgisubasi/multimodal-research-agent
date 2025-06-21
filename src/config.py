from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings - Qdrant Cloud only."""
    
    # File Settings
    upload_dir: Path = Field(default=Path("data/papers"))
    max_file_size: int = Field(default=50 * 1024 * 1024)  # 50MB
    
    # Qdrant Cloud (Required)
    qdrant_url: str = Field(..., description="Qdrant Cloud URL (required)")
    qdrant_api_key: str = Field(..., description="Qdrant Cloud API key (required)")
    qdrant_collection: str = Field(default="research_papers")
    
    # ColPali Model Settings
    colpali_model: str = Field(default="vidore/colpali")
    device: str = Field(default="cpu")
    
    # API Settings
    app_name: str = Field(default="Research Assistant")
    debug: bool = Field(default=False)
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    
    class Config:
        env_file = ".env"


# Global settings instance
settings = Settings()

# Create upload directory
settings.upload_dir.mkdir(parents=True, exist_ok=True)