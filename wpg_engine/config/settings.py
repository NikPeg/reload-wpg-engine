"""
Application settings using Pydantic Settings
"""


from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration"""

    url: str = Field(default="sqlite:///./wpg_engine.db", description="Database URL")
    echo: bool = Field(default=False, description="Echo SQL queries")

    model_config = SettingsConfigDict(env_prefix="DB_")


class TelegramSettings(BaseSettings):
    """Telegram bot configuration"""

    token: str | None = Field(default=None, description="Telegram bot token")
    webhook_url: str | None = Field(default=None, description="Webhook URL")

    model_config = SettingsConfigDict(env_prefix="TG_")


class VKSettings(BaseSettings):
    """VK bot configuration"""

    token: str | None = Field(default=None, description="VK bot token")
    group_id: int | None = Field(default=None, description="VK group ID")

    model_config = SettingsConfigDict(env_prefix="VK_")


class AISettings(BaseSettings):
    """AI service configuration"""

    openrouter_api_key: str | None = Field(
        default=None, description="OpenRouter API key"
    )
    default_model: str = Field(
        default="anthropic/claude-3-haiku", description="Default AI model"
    )

    model_config = SettingsConfigDict(env_prefix="AI_")


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
    )


# Global settings instance
settings = Settings()
