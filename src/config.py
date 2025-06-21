from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings using Pydantic."""
    
    # File Settings
    upload_dir: Path = Field(default=Path("data/papers"))
    index_dir: Path = Field(default=Path("data/index"))
    max_file_size: int = Field(default=50 * 1024 * 1024)  # 50MB
    
    # Qdrant Vector Database
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_collection: str = Field(default="research_papers")
    
    # ColPali Model Settings
    colpali_model: str = Field(default="vidore/colpali")
    device: str = Field(default="cpu")  # Change to "cuda" if you have GPU
    
    # API Settings
    app_name: str = Field(default="Research Assistant")
    version: str = Field(default="1.0.0")
    debug: bool = Field(default=True)
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    
    # Agent Settings
    max_results: int = Field(default=5)
    similarity_threshold: float = Field(default=0.7)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()

# Create directories if they don't exist
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.index_dir.mkdir(parents=True, exist_ok=True)