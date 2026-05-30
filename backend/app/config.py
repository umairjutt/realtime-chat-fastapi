from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://app:secret@localhost:5432/chat"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "supersecretchangeme"
    jwt_alg: str = "HS256"
    jwt_ttl_seconds: int = 60 * 60 * 24

    class Config:
        env_file = ".env"


settings = Settings()
