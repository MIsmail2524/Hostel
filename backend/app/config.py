from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
_DEV_SECRET = "dev-insecure-" + secrets.token_hex(16)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_prefix="KAMRA_", extra="ignore")

    app_name: str = "Kamra"
    env: str = "development"  # development | test | production
    debug: bool = False
    public_base_url: str = "http://localhost:8090"

    database_url: str = f"sqlite:///{BASE_DIR / 'kamra.db'}"
    redis_url: str | None = None

    jwt_secret: str = _DEV_SECRET
    jwt_issuer: str = "kamra-api"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    otp_ttl_minutes: int = 10
    max_login_failures: int = 5
    lockout_minutes: int = 15

    # Comma-separated in env, e.g. KAMRA_CORS_ORIGINS=https://app.kamra.pk,https://kamra.pk
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:8081", "http://localhost:19006"]
    viewer_frame_ancestors: Annotated[list[str], NoDecode] = ["'self'", "http://localhost:8081"]

    storage_dir: Path = BASE_DIR / "storage"
    max_upload_mb: int = 200
    max_image_mb: int = 15
    max_photos_per_listing: int = 20
    max_inputs_per_room: int = 40
    max_video_seconds: int = 180

    run_worker_in_process: bool = True
    recon_output_width: int = 4096
    gpu_worker_url: str | None = None  # enables the Gaussian-splat engine

    @field_validator("cors_origins", "viewer_frame_ancestors", mode="before")
    @classmethod
    def _split(cls, v):
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def expose_dev_codes(self) -> bool:
        """OTP codes are returned in API responses only in local development/test."""
        return self.env in ("development", "test")

    def validate_for_production(self) -> None:
        if not self.is_production:
            return
        problems = []
        if self.jwt_secret.startswith("dev-insecure-") or len(self.jwt_secret) < 32:
            problems.append("KAMRA_JWT_SECRET must be set to a random value of ≥ 32 chars")
        if self.debug:
            problems.append("KAMRA_DEBUG must be false")
        if "*" in self.cors_origins:
            problems.append("KAMRA_CORS_ORIGINS must not contain '*'")
        if self.database_url.startswith("sqlite"):
            problems.append("Use PostgreSQL in production")
        if not self.public_base_url.startswith("https://"):
            problems.append("KAMRA_PUBLIC_BASE_URL must be https")
        if problems:
            raise RuntimeError("Insecure production configuration: " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.validate_for_production()
    return s
