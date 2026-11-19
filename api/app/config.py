from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Sravanam"
    database_url: str = "postgresql+psycopg://sravanam:CHANGE@db:5432/sravanam"
    jwt_secret: str = "CHANGE_ME"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7
    media_root: str = "/media"
    cors_origins: list[str] = ["*"]

    class Config:
        env_file = ".env"


settings = Settings()