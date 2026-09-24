# app/config/settings.py
# Reads all configuration from environment variables.
# Uses pydantic-settings so values are validated at startup.

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # ---- Provider selection ----
    # Which WhatsApp provider to use: meta | twilio | dialog360
    provider: str = Field(default="meta", alias="PROVIDER")

    # ---- Meta Cloud API credentials ----
    meta_phone_number_id: str = Field(default="", alias="META_PHONE_NUMBER_ID")
    meta_access_token: str = Field(default="", alias="META_ACCESS_TOKEN")
    meta_verify_token: str = Field(default="changeme", alias="META_VERIFY_TOKEN")
    meta_app_secret: str = Field(default="", alias="META_APP_SECRET")

    # ---- Twilio credentials ----
    twilio_account_sid: str = Field(default="", alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str = Field(default="", alias="TWILIO_AUTH_TOKEN")
    twilio_from_number: str = Field(default="", alias="TWILIO_FROM_NUMBER")

    # ---- 360dialog credentials ----
    dialog360_api_key: str = Field(default="", alias="DIALOG360_API_KEY")
    dialog360_url: str = Field(
        default="https://waba.360dialog.io/v1/messages",
        alias="DIALOG360_URL"
    )

    # ---- Mentor settings ----
    mentor_number: str = Field(default="", alias="MENTOR_NUMBER")
    mentor_webhook: str = Field(default="", alias="MENTOR_WEBHOOK")
    mentor_mode_ttl_hours: int = Field(default=24, alias="MENTOR_MODE_TTL_HOURS")

    # ---- AI Mentor via Kiro Gateway ----
    mentor_ai_enabled: bool = Field(default=False, alias="MENTOR_AI_ENABLED")
    kiro_gateway_url: str = Field(default="http://localhost:9000", alias="KIRO_GATEWAY_URL")
    kiro_gateway_api_key: str = Field(default="", alias="KIRO_GATEWAY_API_KEY")
    mentor_system_prompt_path: str = Field(
        default="config/mentor_prompt.txt",
        alias="MENTOR_SYSTEM_PROMPT_PATH"
    )

    # ---- FAQ config file path ----
    faq_config_path: str = Field(default="config/faqs.yaml", alias="FAQ_CONFIG_PATH")

    # ---- Logging ----
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # ---- Admin panel ----
    admin_enabled: bool = Field(default=False, alias="ADMIN_ENABLED")
    admin_token: str = Field(default="", alias="ADMIN_TOKEN")

    # ---- Server ----
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    class Config:
        # Load from .env file if it exists
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Allow both the alias and the field name
        populate_by_name = True


# Create a single global settings instance used everywhere
settings = Settings()
