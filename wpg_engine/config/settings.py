"""
Application settings using Pydantic Settings
"""

import os

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables from .env file
load_dotenv()


class DatabaseSettings(BaseSettings):
    """Database configuration"""

    url: str = Field(default="sqlite:///./wpg_engine.db", description="Database URL")
    echo: bool = Field(default=False, description="Echo SQL queries")

    model_config = SettingsConfigDict(env_prefix="DB_", extra="allow")


class TelegramSettings(BaseSettings):
    """Telegram bot configuration"""

    token: str | None = Field(
        default_factory=lambda: os.getenv("TG_TOKEN"), description="Telegram bot token"
    )
    webhook_url: str | None = Field(
        default_factory=lambda: os.getenv("TG_WEBHOOK_URL"), description="Webhook URL"
    )
    admin_id: int | None = Field(
        default=None,
        alias="TG_ADMIN_ID",
        description="Admin Telegram ID (positive for user, negative for chat)",
    )

    model_config = SettingsConfigDict(env_prefix="TG_", extra="allow")

    def is_admin_chat(self) -> bool:
        """Check if admin_id represents a chat (negative value)"""
        return self.admin_id is not None and self.admin_id < 0

    def is_admin_user(self) -> bool:
        """Check if admin_id represents a user (positive value)"""
        return self.admin_id is not None and self.admin_id > 0


class VKSettings(BaseSettings):
    """VK bot configuration"""

    token: str | None = Field(default=None, description="VK bot token")
    group_id: int | None = Field(default=None, description="VK group ID")

    model_config = SettingsConfigDict(env_prefix="VK_", extra="allow")

    @field_validator("group_id", mode="before")
    @classmethod
    def validate_group_id(cls, v):
        if isinstance(v, str) and v.startswith("your_vk_group_id"):
            return None
        return int(v) if v and str(v).isdigit() else None


class AISettings(BaseSettings):
    """AI service configuration"""

    openrouter_api_key: str | None = Field(
        default=None, description="OpenRouter API key"
    )
    default_model: str = Field(
        default="anthropic/claude-3-haiku", description="Default AI model"
    )

    model_config = SettingsConfigDict(env_prefix="AI_", extra="allow")


class Settings(BaseSettings):
    """Main application settings"""

    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # Sub-settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    vk: VKSettings = Field(default_factory=VKSettings)
    ai: AISettings = Field(default_factory=AISettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields from .env
    )


# Global settings instance
settings = Settings()
