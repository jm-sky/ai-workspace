"""SQLAlchemy database models for authentication.

This module provides SQLAlchemy ORM models for database persistence.
The UserDB model is designed to work with async SQLAlchemy sessions.

Note: This module complements models.py which contains:
- Pydantic models for API validation (User)
- In-memory UserStore for development/testing

For production use, replace UserStore with database operations using UserDB.
"""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserDB(Base):
    """SQLAlchemy User model for database persistence.

    This model represents the user table in the database and provides
    the structure for persistent user data storage.

    Note: If both auth and users modules are loaded, the table will be
    extended with additional fields from the users module (like 'role').

    Attributes:
        id: Unique identifier (ULID format, 36 chars)
        email: User email address (unique, indexed)
        name: User full name
        hashed_password: Bcrypt hashed password
        is_active: Whether the user account is active
        is_admin: Whether the user has administrator privileges
        created_at: Account creation timestamp
        reset_token: Password reset token (JWT)
        reset_token_expiry: Password reset token expiration time
    """

    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # ULID
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=True)  # Nullable for OAuth users
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_owner: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    reset_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    reset_token_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_verification_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_verification_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active_tenant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True)
    active_team_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    # OAuth fields
    oauth_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    oauth_provider_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Billing fields
    openrouter_api_token: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<UserDB(id={self.id}, email={self.email}, name={self.name})>"


class OAuthConnectionDB(Base):
    """SQLAlchemy OAuth Connection model for multiple OAuth providers per user.

    This model allows users to link multiple OAuth providers to their account.
    Each connection represents one OAuth provider linked to a user account.

    Attributes:
        id: Unique identifier (ULID format, 36 chars)
        user_id: Foreign key to users table
        provider: OAuth provider name (google, facebook, etc.)
        provider_id: Provider's unique user ID
        email: Email from OAuth provider (may differ from user's main email)
        name: Name from OAuth provider
        avatar_url: Profile picture URL from OAuth provider
        created_at: Connection creation timestamp
    """

    __tablename__ = "oauth_connections"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # ULID
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    def __repr__(self) -> str:
        return f"<OAuthConnectionDB(id={self.id}, user_id={self.user_id}, provider={self.provider})>"


# UserDB declares FKs to tenants.id / teams.id. Import those models so SQLAlchemy
# metadata can resolve them during flush (CLI / scripts that only load UserDB).
from app.modules.teams import db_models as _teams_db_models  # noqa: E402, F401
from app.modules.tenants import db_models as _tenants_db_models  # noqa: E402, F401
