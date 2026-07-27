"""Application configuration using Pydantic Settings with modular structure."""

import os
from enum import StrEnum
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.helpers import parse_bool_value, parse_list_value

# Shared config for all nested settings
_base_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")


class Environment(StrEnum):
    """Application environment."""

    LOCAL = "local"
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class AppSettings(BaseSettings):
    """Application configuration."""

    model_config = _base_config

    name: str = Field(default="backend", validation_alias="APP_NAME", description="Application name")
    display_name: str = Field(
        default="AI Workspace",
        validation_alias="APP_DISPLAY_NAME",
        description="Application display name for emails and UI",
    )
    version: str = Field(
        default="0.1.2",
        validation_alias="APP_VERSION",
        description="Application version",
    )
    debug: bool = Field(default=False, validation_alias="DEBUG", description="Debug mode")
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        validation_alias="ENVIRONMENT",
        description="Environment (local, development, test, production)",
    )

    item_promotion_threshold: int = Field(
        default=10,
        validation_alias="ITEM_PROMOTION_THRESHOLD",
        description="Number of promotions required to add item to global catalogue",
        gt=0,
    )

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: Environment) -> Environment:
        """Validate environment is one of allowed values."""
        if v not in Environment:
            allowed = {e.value for e in Environment}
            raise ValueError(f"Environment must be one of {allowed}, got: {v}")
        return v


class ServerSettings(BaseSettings):
    """Server configuration."""

    model_config = _base_config

    host: str = Field(default="0.0.0.0", validation_alias="HOST", description="Server host")
    port: int = Field(default=8000, validation_alias="PORT", description="Server port")
    reload: bool = Field(
        default=True,
        validation_alias="RELOAD",
        description="Auto-reload on code changes",
    )
    cors_origins: str | list[str] = Field(
        default='["http://localhost:5176"]',
        validation_alias="CORS_ORIGINS",
        description="Allowed CORS origins",
    )
    cors_credentials: bool = Field(
        default=True,
        validation_alias="CORS_CREDENTIALS",
        description="Allow credentials",
    )
    cors_methods: str | list[str] = Field(
        default='["*"]',
        validation_alias="CORS_METHODS",
        description="Allowed HTTP methods",
    )
    cors_headers: str | list[str] = Field(
        default='["*"]',
        validation_alias="CORS_HEADERS",
        description="Allowed HTTP headers",
    )
    allowed_hosts: str | list[str] = Field(
        default='["localhost", "127.0.0.1"]',
        validation_alias="ALLOWED_HOSTS",
        description="Allowed hosts for TrustedHostMiddleware (production security)",
    )

    @field_validator("cors_origins", "cors_methods", "cors_headers", "allowed_hosts", mode="after")
    @classmethod
    def parse_list_fields(cls, v: str | list[str]) -> list[str]:
        """Parse list fields from JSON array or comma-separated string."""
        return parse_list_value(v)

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port is in valid range."""
        if not 1 <= v <= 65535:
            raise ValueError(f"Port must be between 1 and 65535, got: {v}")
        return v


class DatabaseSettings(BaseSettings):
    """Database configuration."""

    model_config = _base_config

    url: str = Field(
        default="sqlite+aiosqlite:///./data/app.db",
        validation_alias="DATABASE_URL",
        description="Database connection URL",
    )
    pool_size: int = Field(
        default=5,
        validation_alias="DATABASE_POOL_SIZE",
        description="Database connection pool size",
    )
    max_overflow: int = Field(
        default=10,
        validation_alias="DATABASE_MAX_OVERFLOW",
        description="Max database connections overflow",
    )
    pool_recycle: int = Field(
        default=3600,
        validation_alias="DATABASE_POOL_RECYCLE",
        description="Database pool recycle time (seconds)",
    )
    echo: bool = Field(default=False, validation_alias="DATABASE_ECHO", description="Echo SQL queries")

    @field_validator("url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL format."""
        if not v:
            raise ValueError("Database URL cannot be empty")
        # Support both sqlite and postgresql
        if not (v.startswith("sqlite") or v.startswith("postgresql")):
            raise ValueError("Only SQLite and PostgreSQL databases are supported")
        return v


class SecuritySettings(BaseSettings):
    """Security and authentication configuration."""

    model_config = _base_config

    secret_key: str = Field(
        default="change-me-in-production-min-32-chars!",
        validation_alias="SECRET_KEY",
        description="Secret key for JWT and other crypto operations",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        validation_alias="JWT_ALGORITHM",
        description="JWT signing algorithm",
    )
    jwt_issuer: str = Field(
        default="ai-workspace",
        validation_alias="JWT_ISSUER",
        description="JWT 'iss' claim; verified on decode to bind tokens to this deployment",
    )
    jwt_audience: str = Field(
        default="ai-workspace",
        validation_alias="JWT_AUDIENCE",
        description="JWT 'aud' claim; verified on decode to bind tokens to this deployment",
    )
    access_token_expires_minutes: int = Field(
        default=30,
        validation_alias="ACCESS_TOKEN_EXPIRES_MINUTES",
        description="Access token expiration in minutes",
    )
    refresh_token_expires_days: int = Field(
        default=7,
        validation_alias="REFRESH_TOKEN_EXPIRES_DAYS",
        description="Refresh token expiration in days",
    )
    password_reset_token_expires_hours: int = Field(
        default=1,
        validation_alias="PASSWORD_RESET_TOKEN_EXPIRES_HOURS",
        description="Password reset token expiration in hours",
    )
    email_verification_token_expires_hours: int = Field(
        default=24,
        validation_alias="EMAIL_VERIFICATION_TOKEN_EXPIRES_HOURS",
        description="Email verification token expiration in hours",
    )
    superadmin_email: str | None = Field(
        default=None,
        validation_alias="SUPERADMIN_EMAIL",
        description="Email address of the super admin user (owner) - cannot be deleted or demoted",
    )
    protected_user_email: str | None = Field(
        default=None,
        validation_alias="PROTECTED_USER_EMAIL",
        description="Protected user email - this user cannot be deleted",
    )

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Validate secret key strength and security."""
        if "change-me" in v.lower() or "change-this" in v.lower():
            raise ValueError("Secret key must be changed from default value in production. " "Set SECRET_KEY environment variable with a secure random string.")

        if len(v) < 32:
            raise ValueError("Secret key must be at least 32 characters long for security. " "Use a cryptographically secure random string.")

        # Check for basic entropy (not all same character)
        if len(set(v)) < 8:
            raise ValueError("Secret key must have sufficient entropy. " "Use a truly random string with varied characters.")

        return v


class RateLimitSettings(BaseSettings):
    """Rate limiting configuration."""

    model_config = _base_config

    enabled: bool = Field(
        default=True,
        validation_alias="RATE_LIMIT_ENABLED",
        description="Enable rate limiting",
    )
    default_per_minute: int = Field(
        default=60,
        validation_alias="RATE_LIMIT_DEFAULT_PER_MINUTE",
        description="Default rate limit per minute",
    )
    default_per_hour: int = Field(
        default=1000,
        validation_alias="RATE_LIMIT_DEFAULT_PER_HOUR",
        description="Default rate limit per hour",
    )
    auth_register: str = Field(
        default="5/minute",
        validation_alias="AUTH_REGISTER_RATE_LIMIT",
        description="Registration rate limit",
    )
    auth_login: str = Field(
        default="10/minute",
        validation_alias="AUTH_LOGIN_RATE_LIMIT",
        description="Login rate limit",
    )
    auth_refresh: str = Field(
        default="20/minute",
        validation_alias="AUTH_REFRESH_RATE_LIMIT",
        description="Token refresh rate limit",
    )
    auth_password_change: str = Field(
        default="3/minute",
        validation_alias="AUTH_PASSWORD_CHANGE_RATE_LIMIT",
        description="Password change rate limit",
    )


class LoggingSettings(BaseSettings):
    """Logging configuration."""

    model_config = _base_config

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO", validation_alias="LOG_LEVEL", description="Logging level")
    format: str = Field(
        default="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        validation_alias="LOG_FORMAT",
        description="Log format",
    )
    file: str | None = Field(default=None, validation_alias="LOG_FILE", description="Log file path")


class RecaptchaSettings(BaseSettings):
    """Google reCAPTCHA v3 configuration."""

    model_config = _base_config

    enabled: bool = Field(
        default=False,
        validation_alias="RECAPTCHA_ENABLED",
        description="Enable reCAPTCHA verification (optional security feature)",
    )
    secret_key: str = Field(
        default="",
        validation_alias="RECAPTCHA_SECRET_KEY",
        description="Google reCAPTCHA v3 secret key",
    )
    site_key: str = Field(
        default="",
        validation_alias="RECAPTCHA_SITE_KEY",
        description="Google reCAPTCHA v3 site key (for frontend)",
    )
    min_score: float = Field(
        default=0.5,
        validation_alias="RECAPTCHA_MIN_SCORE",
        description="Minimum reCAPTCHA score to accept (0.0-1.0)",
    )
    verify_url: str = Field(
        default="https://www.google.com/recaptcha/api/siteverify",
        validation_alias="RECAPTCHA_VERIFY_URL",
        description="reCAPTCHA verification endpoint",
    )

    @field_validator("enabled", mode="before")
    @classmethod
    def parse_enabled(cls, v: str | bool) -> bool:
        """Parse enabled field from string or bool."""
        return parse_bool_value(v)

    @field_validator("min_score")
    @classmethod
    def validate_min_score(cls, v: float) -> float:
        """Validate reCAPTCHA score is in valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"reCAPTCHA min_score must be between 0.0 and 1.0, got: {v}")
        return v


class OAuthSettings(BaseSettings):
    """OAuth authentication configuration."""

    model_config = _base_config

    # Google OAuth
    google_client_id: str = Field(
        default="",
        validation_alias="GOOGLE_OAUTH_CLIENT_ID",
        description="Google OAuth client ID",
    )
    google_client_secret: str = Field(
        default="",
        validation_alias="GOOGLE_OAUTH_CLIENT_SECRET",
        description="Google OAuth client secret",
    )
    google_redirect_uri: str = Field(
        default="",
        validation_alias="GOOGLE_OAUTH_REDIRECT_URI",
        description="Google OAuth redirect URI",
    )

    # Facebook OAuth
    facebook_client_id: str = Field(
        default="",
        validation_alias="FACEBOOK_OAUTH_CLIENT_ID",
        description="Facebook OAuth client ID (App ID)",
    )
    facebook_client_secret: str = Field(
        default="",
        validation_alias="FACEBOOK_OAUTH_CLIENT_SECRET",
        description="Facebook OAuth client secret (App Secret)",
    )
    facebook_redirect_uri: str = Field(
        default="",
        validation_alias="FACEBOOK_OAUTH_REDIRECT_URI",
        description="Facebook OAuth redirect URI",
    )

    # GitHub login (GitHub App user-to-server or OAuth App)
    github_client_id: str = Field(
        default="",
        validation_alias="GITHUB_OAUTH_CLIENT_ID",
        description="GitHub App OAuth client ID for login",
    )
    github_client_secret: str = Field(
        default="",
        validation_alias="GITHUB_OAUTH_CLIENT_SECRET",
        description="GitHub App OAuth client secret for login",
    )
    github_redirect_uri: str = Field(
        default="",
        validation_alias="GITHUB_OAUTH_REDIRECT_URI",
        description="GitHub login callback URL (e.g. /auth/callback/github)",
    )


class EmailSettings(BaseSettings):
    """Email service configuration."""

    model_config = _base_config

    enabled: bool = Field(
        default=True,
        validation_alias="EMAIL_ENABLED",
        description="Enable email service",
    )
    adapter: Literal["file", "smtp"] = Field(
        default="file",
        validation_alias="EMAIL_ADAPTER",
        description="Email adapter type (file or smtp)",
    )
    file_path: str = Field(
        default="./emails",
        validation_alias="EMAIL_FILE_PATH",
        description="Path for file email adapter",
    )
    smtp_host: str = Field(
        default="localhost",
        validation_alias="SMTP_HOST",
        description="SMTP server host",
    )
    smtp_port: int = Field(default=587, validation_alias="SMTP_PORT", description="SMTP server port")
    smtp_user: str = Field(default="", validation_alias="SMTP_USER", description="SMTP username")
    smtp_password: str = Field(default="", validation_alias="SMTP_PASSWORD", description="SMTP password")
    smtp_from: str = Field(
        default="noreply@example.com",
        validation_alias="SMTP_FROM",
        description="Default from email address",
    )
    smtp_use_tls: bool = Field(
        default=True,
        validation_alias="SMTP_USE_TLS",
        description="Use TLS for SMTP connection",
    )
    enable_audit: bool = Field(
        default=True,
        validation_alias="EMAIL_ENABLE_AUDIT",
        description="Enable email audit logging to database",
    )
    enable_retry: bool = Field(
        default=False,
        validation_alias="EMAIL_ENABLE_RETRY",
        description="Enable retry logic for SMTP (with exponential backoff)",
    )
    max_retries: int = Field(
        default=5,
        validation_alias="EMAIL_MAX_RETRIES",
        description="Maximum retry attempts for SMTP",
    )


class StorageSettings(BaseSettings):
    """Storage configuration for file uploads."""

    model_config = _base_config

    # Storage type
    type: Literal["local", "s3"] = Field(
        default="local",
        validation_alias="STORAGE_TYPE",
        description="Storage backend type (local or s3)",
    )

    # Local storage
    local_path: str = Field(
        default="./uploads",
        validation_alias="STORAGE_LOCAL_PATH",
        description="Local storage base path",
    )
    base_url: str | None = Field(
        default=None,
        validation_alias="STORAGE_BASE_URL",
        description="Base URL for serving uploaded files (e.g., https://api.ai-workspace.dev-made.it or http://localhost:8003). If not set, uses relative paths.",
    )

    # S3 storage
    s3_bucket: str = Field(
        default="",
        validation_alias="STORAGE_S3_BUCKET",
        description="S3 bucket name",
    )
    s3_access_key: str = Field(
        default="",
        validation_alias="STORAGE_S3_ACCESS_KEY",
        description="S3 access key ID",
    )
    s3_secret_key: str = Field(
        default="",
        validation_alias="STORAGE_S3_SECRET_KEY",
        description="S3 secret access key",
    )
    s3_region: str = Field(
        default="us-east-1",
        validation_alias="STORAGE_S3_REGION",
        description="S3 region",
    )
    s3_endpoint_url: str | None = Field(
        default=None,
        validation_alias="STORAGE_S3_ENDPOINT_URL",
        description="S3 endpoint URL (for S3-compatible services)",
    )
    s3_public_endpoint_url: str | None = Field(
        default=None,
        validation_alias="STORAGE_S3_PUBLIC_ENDPOINT_URL",
        description="Public S3 endpoint URL for generating accessible URLs (e.g., http://localhost:9000 for MinIO in Docker). If not set, uses s3_endpoint_url.",
    )

    # Upload limits
    max_file_size: int = Field(
        default=20 * 1024 * 1024,  # 20 MB (default for regular users)
        validation_alias="STORAGE_MAX_FILE_SIZE",
        description="Maximum file size in bytes (default for regular users, admins have 50 MB)",
    )
    max_file_size_admin: int = Field(
        default=50 * 1024 * 1024,  # 50 MB (for admins)
        validation_alias="STORAGE_MAX_FILE_SIZE_ADMIN",
        description="Maximum file size in bytes for administrators",
    )
    max_files_per_item: int = Field(
        default=10,
        validation_alias="STORAGE_MAX_FILES_PER_ITEM",
        description="Maximum number of images per item",
    )
    allowed_mime_types: str | list[str] = Field(
        default='["image/jpeg", "image/png", "image/webp", "image/gif"]',
        validation_alias="STORAGE_ALLOWED_MIME_TYPES",
        description="Allowed MIME types for uploads",
    )

    # Image processing
    enable_processing: bool = Field(
        default=True,
        validation_alias="STORAGE_ENABLE_PROCESSING",
        description="Enable auto-resize and optimization",
    )
    max_width: int = Field(
        default=1920,
        validation_alias="STORAGE_MAX_WIDTH",
        description="Maximum image width (auto-resize)",
    )
    max_height: int = Field(
        default=1920,
        validation_alias="STORAGE_MAX_HEIGHT",
        description="Maximum image height (auto-resize)",
    )
    jpeg_quality: int = Field(
        default=85,
        validation_alias="STORAGE_JPEG_QUALITY",
        description="JPEG compression quality (1-100)",
    )
    convert_to_webp: bool = Field(
        default=False,
        validation_alias="STORAGE_CONVERT_TO_WEBP",
        description="Convert images to WebP format",
    )

    @field_validator("allowed_mime_types", mode="after")
    @classmethod
    def parse_mime_types(cls, v: str | list[str]) -> list[str]:
        """Parse MIME types from JSON array or comma-separated string."""
        return parse_list_value(v)

    @field_validator("jpeg_quality")
    @classmethod
    def validate_jpeg_quality(cls, v: int) -> int:
        """Validate JPEG quality is in valid range."""
        if not 1 <= v <= 100:
            raise ValueError(f"JPEG quality must be between 1 and 100, got: {v}")
        return v


class AttachmentSettings(BaseSettings):
    """Chat attachment upload limits and processing."""

    model_config = _base_config

    max_file_bytes: int = Field(
        default=10 * 1024 * 1024,
        validation_alias="ATTACHMENT_MAX_FILE_BYTES",
        description="Max bytes per chat attachment (stream-enforced)",
        gt=0,
    )
    max_per_message: int = Field(
        default=5,
        validation_alias="ATTACHMENT_MAX_PER_MESSAGE",
        description="Max attachments per chat message",
        gt=0,
    )
    max_total_bytes: int = Field(
        default=25 * 1024 * 1024,
        validation_alias="ATTACHMENT_MAX_TOTAL_BYTES",
        description="Max total attachment bytes per chat message",
        gt=0,
    )
    max_text_chars: int = Field(
        default=100_000,
        validation_alias="ATTACHMENT_MAX_TEXT_CHARS",
        description="Max extracted text characters kept for model context",
        gt=0,
    )
    pdf_max_pages: int = Field(
        default=50,
        validation_alias="ATTACHMENT_PDF_MAX_PAGES",
        description="Max PDF pages to extract",
        gt=0,
    )
    model_max_edge: int = Field(
        default=1536,
        validation_alias="ATTACHMENT_MODEL_MAX_EDGE",
        description="Max image edge length sent to the model",
        gt=0,
    )
    thumbnail_max_edge: int = Field(
        default=320,
        validation_alias="ATTACHMENT_THUMBNAIL_MAX_EDGE",
        description="Max thumbnail edge length",
        gt=0,
    )
    upload_rate_limit: str = Field(
        default="30/minute",
        validation_alias="ATTACHMENT_UPLOAD_RATE_LIMIT",
        description="SlowAPI rate limit string for attachment upload",
    )
    orphan_ttl_hours: int = Field(
        default=24,
        validation_alias="ATTACHMENT_ORPHAN_TTL_HOURS",
        description="Hours before unbound (run_id NULL) attachments are purged",
        gt=0,
    )


class SentrySettings(BaseSettings):
    """Sentry error monitoring configuration."""

    model_config = _base_config

    enabled: bool = Field(
        default=False,
        validation_alias="SENTRY_ENABLED",
        description="Enable Sentry error monitoring",
    )
    dsn: str = Field(
        default="",
        validation_alias="SENTRY_DSN",
        description="Sentry DSN (Data Source Name) for error reporting",
    )
    environment: str = Field(
        default="development",
        validation_alias="SENTRY_ENVIRONMENT",
        description="Environment name for Sentry (development, staging, production)",
    )
    traces_sample_rate: float = Field(
        default=1.0,
        validation_alias="SENTRY_TRACES_SAMPLE_RATE",
        description="Performance monitoring sample rate (0.0-1.0)",
    )
    profiles_sample_rate: float = Field(
        default=1.0,
        validation_alias="SENTRY_PROFILES_SAMPLE_RATE",
        description="Profiling sample rate (0.0-1.0)",
    )
    release: str | None = Field(
        default=None,
        validation_alias="SENTRY_RELEASE",
        description="Release version for Sentry (e.g., git commit SHA or version number)",
    )

    @field_validator("enabled", mode="before")
    @classmethod
    def parse_enabled(cls, v: str | bool) -> bool:
        """Parse enabled field from string or bool."""
        return parse_bool_value(v)

    @field_validator("traces_sample_rate", "profiles_sample_rate")
    @classmethod
    def validate_sample_rate(cls, v: float) -> float:
        """Validate sample rate is in valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Sample rate must be between 0.0 and 1.0, got: {v}")
        return v


class AISettings(BaseSettings):
    """AI configuration for OpenRouter integration."""

    model_config = _base_config

    enabled: bool = Field(default=True, validation_alias="AI_ENABLED", description="Enable AI features")
    openrouter_api_key: str = Field(
        default="",
        validation_alias="OPENROUTER_API_KEY",
        description="OpenRouter API key",
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        validation_alias="OPENROUTER_BASE_URL",
        description="OpenRouter base URL",
    )
    token_encryption_key: str = Field(
        default="",
        validation_alias="AI_TOKEN_ENCRYPTION_KEY",
        description="Fernet encryption key for API tokens",
    )
    cache_enabled: bool = Field(
        default=True,
        validation_alias="AI_CACHE_ENABLED",
        description="Enable PostgreSQL caching",
    )
    cache_ttl_classify: int = Field(
        default=7,
        validation_alias="AI_CACHE_TTL_CLASSIFY",
        description="Cache TTL for classification (days)",
    )
    cache_ttl_embed: int = Field(
        default=30,
        validation_alias="AI_CACHE_TTL_EMBED",
        description="Cache TTL for embeddings (days)",
    )
    catalog_cache_ttl: int = Field(
        default=21600,
        validation_alias="AI_CATALOG_CACHE_TTL",
        description="Redis TTL for the OpenRouter model catalog (seconds)",
        gt=0,
    )
    catalog_fetch_timeout: float = Field(
        default=10.0,
        validation_alias="AI_CATALOG_FETCH_TIMEOUT",
        description="Timeout for fetching the OpenRouter model catalog (seconds)",
        gt=0,
    )
    agent_max_steps: int = Field(
        default=10,
        validation_alias="AGENT_MAX_STEPS",
        description="Maximum tool-calling loop iterations per agent run",
        gt=0,
    )
    tool_search_enabled: bool = Field(
        default=True,
        validation_alias="TOOL_SEARCH_ENABLED",
        description="Enable dynamic tool search when the catalog exceeds the threshold",
    )
    tool_search_threshold: int = Field(
        default=15,
        validation_alias="TOOL_SEARCH_THRESHOLD",
        description="Above this tool count, only core tools + tool_search are loaded initially",
        gt=0,
    )
    tool_search_top_k: int = Field(
        default=5,
        validation_alias="TOOL_SEARCH_TOP_K",
        description="Max tools activated per tool_search call",
        gt=0,
    )
    memory_enabled: bool = Field(
        default=True,
        validation_alias="AI_MEMORY_ENABLED",
        description="Enable semantic memory storage and injection",
    )
    memory_embedding_model: str = Field(
        default="openai/text-embedding-3-small",
        validation_alias="AI_MEMORY_EMBEDDING_MODEL",
        description="Embedding model on OpenRouter for memory vectors",
    )
    memory_embedding_dimensions: int = Field(
        default=1536,
        validation_alias="AI_MEMORY_EMBEDDING_DIMENSIONS",
        description="Vector dimensions for memory embeddings",
        gt=0,
    )
    memory_similarity_threshold: float = Field(
        default=0.55,
        validation_alias="AI_MEMORY_SIMILARITY_THRESHOLD",
        description="Minimum cosine similarity for memory retrieval",
        ge=0.0,
        le=1.0,
    )
    memory_injection_limit: int = Field(
        default=5,
        validation_alias="AI_MEMORY_INJECTION_LIMIT",
        description="Max memories auto-injected into agent system prompt",
        ge=0,
        le=20,
    )
    rag_chunk_size: int = Field(
        default=1200,
        validation_alias="AI_RAG_CHUNK_SIZE",
        description="Character window size for RAG document chunking",
        gt=0,
    )
    rag_chunk_overlap: int = Field(
        default=150,
        validation_alias="AI_RAG_CHUNK_OVERLAP",
        description="Character overlap between consecutive RAG chunks",
        ge=0,
    )
    rag_max_chunks_per_document: int = Field(
        default=200,
        validation_alias="AI_RAG_MAX_CHUNKS_PER_DOCUMENT",
        description="Hard cap on chunks created per ingested document",
        gt=0,
    )
    rag_similarity_threshold: float = Field(
        default=0.5,
        validation_alias="AI_RAG_SIMILARITY_THRESHOLD",
        description="Minimum cosine similarity for RAG chunk retrieval",
        ge=0.0,
        le=1.0,
    )
    rag_search_limit: int = Field(
        default=8,
        validation_alias="AI_RAG_SEARCH_LIMIT",
        description="Default max chunks returned by rag_search",
        ge=1,
        le=50,
    )
    audit_raw_enabled: bool = Field(
        default=True,
        validation_alias="AI_AUDIT_RAW_ENABLED",
        description="Persist full (raw) tool payloads in a separate audit tier",
    )
    audit_raw_retention_days: int = Field(
        default=30,
        validation_alias="AI_AUDIT_RAW_RETENTION_DAYS",
        description="Days to keep raw agent trace payloads before purge/expiry",
        ge=0,
    )
    embedding_model: str = Field(
        default="openai/text-embedding-3-small",
        validation_alias="AI_EMBEDDING_MODEL",
        description="Embedding model on OpenRouter (replaces AI_MEMORY_EMBEDDING_MODEL, which is now a deprecated alias)",
    )
    embedding_dimensions: int = Field(
        default=1536,
        validation_alias="AI_EMBEDDING_DIMENSIONS",
        description="Vector dimensions for embeddings; must match the pgvector column width",
        gt=0,
    )
    embedding_version: int = Field(
        default=1,
        validation_alias="AI_EMBEDDING_VERSION",
        description="Bump when the embedding model changes; reembed CLI resumes from this version",
        gt=0,
    )
    embedding_batch_size: int = Field(
        default=64,
        validation_alias="AI_EMBEDDING_BATCH_SIZE",
        description="Batch size used by EmbeddingService.embed_batch()",
        gt=0,
    )
    rag_hybrid_enabled: bool = Field(
        default=True,
        validation_alias="AI_RAG_HYBRID_ENABLED",
        description="Combine dense (vector) and lexical (tsvector) search via RRF",
    )
    rag_rrf_k: int = Field(
        default=60,
        validation_alias="AI_RAG_RRF_K",
        description="RRF constant k in score = sum(1 / (k + rank))",
        gt=0,
    )
    rag_fts_config: str = Field(
        default="auto",
        validation_alias="AI_RAG_FTS_CONFIG",
        description="Postgres text-search config: 'auto' detects 'polish', falling back to 'simple'",
    )
    rag_rerank_enabled: bool = Field(
        default=False,
        validation_alias="AI_RAG_RERANK_ENABLED",
        description="Use HostedReranker instead of NoopReranker",
    )
    rag_rerank_url: str = Field(
        default="",
        validation_alias="AI_RAG_RERANK_URL",
        description="Hosted reranker HTTP endpoint",
    )
    rag_rerank_model: str = Field(
        default="",
        validation_alias="AI_RAG_RERANK_MODEL",
        description="Hosted reranker model identifier",
    )
    rag_rerank_api_key: str = Field(
        default="",
        validation_alias="AI_RAG_RERANK_API_KEY",
        description="Hosted reranker API key",
    )
    rag_rerank_candidates: int = Field(
        default=50,
        validation_alias="AI_RAG_RERANK_CANDIDATES",
        description="Top-N candidates retrieved before reranking down to rag_search_limit",
        gt=0,
    )
    memory_dedupe_threshold: float = Field(
        default=0.92,
        validation_alias="AI_MEMORY_DEDUPE_THRESHOLD",
        description="Cosine similarity above which memory_save treats content as a duplicate",
        ge=0.0,
        le=1.0,
    )
    memory_backend: str = Field(
        default="pgvector",
        validation_alias="MEMORY_BACKEND",
        description="Memory persistence backend: pgvector (default) or graphiti",
    )

    @field_validator("memory_backend")
    @classmethod
    def validate_memory_backend(cls, v: str) -> str:
        allowed = {"pgvector", "graphiti"}
        if v not in allowed:
            raise ValueError(
                f"MEMORY_BACKEND must be one of {sorted(allowed)}, got: {v!r}"
            )
        return v

    @field_validator(
        "enabled",
        "cache_enabled",
        "memory_enabled",
        "audit_raw_enabled",
        "tool_search_enabled",
        "rag_hybrid_enabled",
        "rag_rerank_enabled",
        mode="before",
    )
    @classmethod
    def parse_bool_field(cls, v: str | bool) -> bool:
        """Parse boolean field from string or bool."""
        return parse_bool_value(v)

    @model_validator(mode="after")
    def apply_legacy_embedding_aliases(self) -> "AISettings":
        """Honor AI_MEMORY_EMBEDDING_* when the new AI_EMBEDDING_* keys are unset.

        Keeps existing deployments (e.g. the VPS .env) working unchanged while
        AI_EMBEDDING_* becomes the canonical name (plan 009 dec. #4).
        """
        if "AI_EMBEDDING_MODEL" not in os.environ and "AI_MEMORY_EMBEDDING_MODEL" in os.environ:
            self.embedding_model = self.memory_embedding_model
        if "AI_EMBEDDING_DIMENSIONS" not in os.environ and "AI_MEMORY_EMBEDDING_DIMENSIONS" in os.environ:
            self.embedding_dimensions = self.memory_embedding_dimensions
        return self


class RedisSettings(BaseSettings):
    """Redis configuration for token blacklist and challenge storage."""

    model_config = _base_config

    url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias="REDIS_URL",
        description="Redis connection URL",
    )
    token_blacklist_prefix: str = Field(
        default="blacklist:token:",
        validation_alias="REDIS_TOKEN_BLACKLIST_PREFIX",
        description="Redis key prefix for token blacklist",
    )
    webauthn_challenge_prefix: str = Field(
        default="webauthn:challenge:",
        validation_alias="REDIS_WEBAUTHN_CHALLENGE_PREFIX",
        description="Redis key prefix for WebAuthn challenges",
    )
    webauthn_challenge_ttl: int = Field(
        default=300,
        validation_alias="REDIS_WEBAUTHN_CHALLENGE_TTL",
        description="WebAuthn challenge TTL in seconds (default: 5 minutes)",
    )


class WebAuthnSettings(BaseSettings):
    """WebAuthn configuration."""

    model_config = _base_config

    rp_id: str = Field(
        default="localhost",
        validation_alias="WEBAUTHN_RP_ID",
        description="WebAuthn Relying Party ID (domain)",
    )
    rp_name: str = Field(
        default="AI Workspace",
        validation_alias="WEBAUTHN_RP_NAME",
        description="WebAuthn Relying Party Name",
    )
    origin: str = Field(
        default="http://localhost:5176",
        validation_alias="WEBAUTHN_ORIGIN",
        description="WebAuthn expected origin (frontend URL)",
    )


class StripeSettings(BaseSettings):
    """Stripe billing configuration."""

    model_config = _base_config

    enabled: bool = Field(
        default=False,
        validation_alias="STRIPE_ENABLED",
        description="Enable Stripe billing integration",
    )
    secret_key: str = Field(
        default="",
        validation_alias="STRIPE_SECRET_KEY",
        description="Stripe secret API key",
    )
    publishable_key: str = Field(
        default="",
        validation_alias="STRIPE_PUBLISHABLE_KEY",
        description="Stripe publishable API key",
    )
    webhook_secret: str = Field(
        default="",
        validation_alias="STRIPE_WEBHOOK_SECRET",
        description="Stripe webhook signing secret",
    )

    # Price IDs (configured in Stripe Dashboard)
    pro_monthly_price_id: str = Field(
        default="",
        validation_alias="STRIPE_PRO_MONTHLY_PRICE_ID",
        description="Stripe price ID for Pro monthly subscription",
    )
    pro_annual_price_id: str = Field(
        default="",
        validation_alias="STRIPE_PRO_ANNUAL_PRICE_ID",
        description="Stripe price ID for Pro annual subscription",
    )
    pro_plus_monthly_price_id: str = Field(
        default="",
        validation_alias="STRIPE_PRO_PLUS_MONTHLY_PRICE_ID",
        description="Stripe price ID for Pro Plus monthly subscription",
    )
    pro_plus_annual_price_id: str = Field(
        default="",
        validation_alias="STRIPE_PRO_PLUS_ANNUAL_PRICE_ID",
        description="Stripe price ID for Pro Plus annual subscription",
    )

    @field_validator("enabled", mode="before")
    @classmethod
    def parse_enabled(cls, v: str | bool) -> bool:
        """Parse enabled field from string or bool."""
        return parse_bool_value(v)


class WorkspaceSettings(BaseSettings):
    """Default workspace configuration (app-level ceiling)."""

    model_config = _base_config

    default_allowed_models: str | list[str] = Field(
        default_factory=list,
        validation_alias="WORKSPACE_DEFAULT_ALLOWED_MODELS",
        description=("App-level allow-list of LLM model IDs. Empty means no ceiling: the " "whole catalog is available and only tenant/team/user narrow it."),
    )
    default_model: str = Field(
        default="qwen/qwen3.7-plus",
        validation_alias="WORKSPACE_DEFAULT_MODEL",
        description="Default LLM model ID",
    )
    default_max_tokens: int = Field(
        default=32000,
        validation_alias="WORKSPACE_DEFAULT_MAX_TOKENS",
        description="Default max output tokens ceiling",
    )
    default_rag_enabled: bool = Field(
        default=False,
        validation_alias="WORKSPACE_DEFAULT_RAG_ENABLED",
        description="Whether RAG is enabled by default",
    )
    default_tools_enabled: bool = Field(
        default=True,
        validation_alias="WORKSPACE_DEFAULT_TOOLS_ENABLED",
        description="Whether agent tools are enabled by default",
    )

    @field_validator("default_allowed_models", mode="after")
    @classmethod
    def parse_allowed_models(cls, v: str | list[str]) -> list[str]:
        return parse_list_value(v)

    @field_validator("default_rag_enabled", "default_tools_enabled", mode="before")
    @classmethod
    def parse_workspace_bools(cls, v: str | bool) -> bool:
        return parse_bool_value(v)


class IntegrationSettings(BaseSettings):
    """Per-user integration OAuth token vault and provider API configuration."""

    model_config = _base_config

    token_encryption_key: str = Field(
        default="",
        validation_alias="INTEGRATION_TOKEN_ENCRYPTION_KEY",
        description="Fernet key for integration OAuth tokens (Jira, GitLab, etc.)",
    )
    jira_base_url: str = Field(
        default="",
        validation_alias="JIRA_BASE_URL",
        description="Jira Cloud/Server base URL (e.g. https://company.atlassian.net)",
    )
    jira_client_field: str = Field(
        default="customfield_10001",
        validation_alias="JIRA_CLIENT_FIELD",
        description="Jira custom field ID for Klient / client name",
    )
    gitlab_base_url: str = Field(
        default="",
        validation_alias="GITLAB_BASE_URL",
        description="GitLab instance base URL (e.g. https://gitlab.com)",
    )
    github_oauth_client_id: str = Field(
        default="",
        validation_alias="GITHUB_INTEGRATION_OAUTH_CLIENT_ID",
        description="GitHub App OAuth client ID (user-to-server flow)",
    )
    github_oauth_client_secret: str = Field(
        default="",
        validation_alias="GITHUB_INTEGRATION_OAUTH_CLIENT_SECRET",
        description="GitHub App OAuth client secret",
    )
    github_oauth_redirect_uri: str = Field(
        default="",
        validation_alias="GITHUB_INTEGRATION_OAUTH_REDIRECT_URI",
        description="GitHub App OAuth callback URL (frontend route)",
    )
    github_app_id: str = Field(
        default="",
        validation_alias="GITHUB_APP_ID",
        description="GitHub App ID (numeric) — enables App-specific OAuth behavior",
    )
    gmail_oauth_client_id: str = Field(
        default="",
        validation_alias="GMAIL_INTEGRATION_OAUTH_CLIENT_ID",
        description="Google OAuth client ID for Gmail integration",
    )
    gmail_oauth_client_secret: str = Field(
        default="",
        validation_alias="GMAIL_INTEGRATION_OAUTH_CLIENT_SECRET",
        description="Google OAuth client secret for Gmail integration",
    )
    gmail_oauth_redirect_uri: str = Field(
        default="",
        validation_alias="GMAIL_INTEGRATION_OAUTH_REDIRECT_URI",
        description="Gmail integration OAuth callback URL (frontend route)",
    )


class HealthSettings(BaseSettings):
    """Health/monitoring configuration (Ops Monitor integration)."""

    model_config = _base_config

    details_token: str = Field(
        default="",
        validation_alias="HEALTH_DETAILS_TOKEN",
        description="Bearer token required to access GET /api/health/details (Ops Monitor)",
    )


class Settings(BaseSettings):
    """
    Main application settings composed of nested configuration classes.

    All settings can be overridden via environment variables.
    Use nested structure for better organization and clarity.
    """

    model_config = _base_config

    # Nested settings
    app: AppSettings = Field(default_factory=AppSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    recaptcha: RecaptchaSettings = Field(default_factory=RecaptchaSettings)
    oauth: OAuthSettings = Field(default_factory=OAuthSettings)
    email: EmailSettings = Field(default_factory=EmailSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    attachments: AttachmentSettings = Field(default_factory=AttachmentSettings)
    sentry: SentrySettings = Field(default_factory=SentrySettings)
    ai: AISettings = Field(default_factory=AISettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    webauthn: WebAuthnSettings = Field(default_factory=WebAuthnSettings)
    stripe: StripeSettings = Field(default_factory=StripeSettings)
    health: HealthSettings = Field(default_factory=HealthSettings)
    workspace: WorkspaceSettings = Field(default_factory=WorkspaceSettings)
    integrations: IntegrationSettings = Field(default_factory=IntegrationSettings)

    # Legacy compatibility - still accessible at root level
    frontend_url: str = Field(
        default="http://localhost:5176",
        validation_alias="FRONTEND_URL",
        description="Frontend application URL for reset links and redirects",
    )

    # Convenience methods
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app.environment in (Environment.LOCAL, Environment.DEVELOPMENT)

    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.app.environment == Environment.PRODUCTION

    def is_test(self) -> bool:
        """Check if running in test mode."""
        return self.app.environment == Environment.TEST

    def validate_production(self) -> None:
        """Assert production-safe invariants; raise ``ValueError`` on violation.

        Call once on startup (see app_factory) when ``is_production()``. This is a
        defence-in-depth guardrail against deploying with insecure defaults:

        - ``DEBUG`` must be off (leaks stack traces / error details).
        - ``ALLOWED_HOSTS`` must be a non-empty explicit allow-list (TrustedHost).
        - ``CORS_ORIGINS`` must be a non-empty explicit allow-list, never ``*``
          (a wildcard origin with credentials is a real CSRF/exfiltration hole).

        The secret-key strength is already enforced at field-validation time.
        """
        if not self.is_production():
            return

        errors: list[str] = []

        if self.app.debug:
            errors.append("DEBUG must be false in production (set DEBUG=false).")

        # allowed_hosts / cors_origins are parsed to lists by their validators.
        allowed_hosts = self.server.allowed_hosts
        if not allowed_hosts or "*" in allowed_hosts:
            errors.append("ALLOWED_HOSTS must be a non-empty explicit allow-list " "(no '*') in production.")

        cors_origins = self.server.cors_origins
        if not cors_origins:
            errors.append("CORS_ORIGINS must be set to an explicit allow-list.")
        elif "*" in cors_origins:
            errors.append("CORS_ORIGINS must not contain '*' in production " "(wildcard origins with credentials are unsafe).")

        if errors:
            raise ValueError("Insecure production configuration detected:\n- " + "\n- ".join(errors))


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
