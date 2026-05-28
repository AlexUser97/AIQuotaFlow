from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    reminder_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    notifications_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    time_format_24h: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    sort_mode: Mapped[str] = mapped_column(
        String(32), default="status", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    subscriptions: Mapped[list["SubscriptionAccount"]] = relationship(  # noqa: F821
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    purposes: Mapped[list["Purpose"]] = relationship(  # noqa: F821
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
