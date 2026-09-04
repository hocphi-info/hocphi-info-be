"""Cau hinh ung dung — doc tu bien moi truong / file .env.

`pydantic-settings` la cach FastAPI doc config: khai bao 1 class co kieu, moi
thuoc tinh la 1 bien env. Pydantic tu ep kieu (str -> int, "a,b" -> list...) va
bao loi ngay luc khoi dong neu thieu bien bat buoc.

Tuong duong: Go dung `os.Getenv` + parse thu cong / `envconfig`.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Postgres — driver asyncpg. Format: postgresql+asyncpg://user:pass@host:port/db
    database_url: str = Field(
        default="postgresql+asyncpg://hocphi:hocphi@localhost:5432/hocphi",
    )
    # Redis — chua dung toi Tuan 5, chi giu bien de compose day du.
    redis_url: str = Field(default="redis://localhost:6379/0")
    # Danh sach origin FE duoc phep goi cheo, ngan cach bang dau phay.
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"],
    )
    # In moi cau SQL ra stdout — bat khi debug, tat o CI/prod.
    sql_echo: bool = Field(default=False)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        """Cho phep dat CORS_ORIGINS="http://a,http://b" trong .env (chuoi CSV)."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    """Doc settings 1 lan roi cache — moi lan goi tra ve cung 1 object."""
    return Settings()


settings = get_settings()
