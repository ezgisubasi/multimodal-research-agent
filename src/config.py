from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # API Keys
    openai_api_key: str = Field(..., description="OpenAI API key")
    
    # Qdrant
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_collection: str = Field(default="research_papers")
    
    # File Settings
    max_file_size: int = Field(default=50 * 1024 * 1024)  # 50MB
    upload_dir: Path = Field(default=Path("data/uploads"))
    processed_dir: Path = Field(default=Path("data/processed"))
    
    # Text Processing
    chunk_size: int = Field(default=1000)
    chunk_overlap: int = Field(default=200)
    
    # App Settings
    debug: bool = Field(default=False)
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    class Config:
        env_file = ".env"


# Global settings instance
settings = Settings()