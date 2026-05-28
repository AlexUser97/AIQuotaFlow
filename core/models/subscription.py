from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

if TYPE_CHECKING:
    from core.models.user import User


class SubscriptionAccount(Base):
    __tablename__ = "subscription_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    login_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    plan: Mapped[str] = mapped_column(String(64), nullable=False)

    current_status: Mapped[str] = mapped_column(
        String(32), default="available", nullable=False
    )

    cooldown_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    subscription_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    owner: Mapped["User"] = relationship(back_populates="subscriptions")
    purposes: Mapped[list["Purpose"]] = relationship(
        secondary="subscription_purposes",
        back_populates="subscriptions",
        lazy="selectin",
    )


class Purpose(Base):
    __tablename__ = "purposes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    owner: Mapped["User"] = relationship(back_populates="purposes")
    subscriptions: Mapped[list[SubscriptionAccount]] = relationship(
        secondary="subscription_purposes",
        back_populates="purposes",
        lazy="selectin",
    )


class SubscriptionPurpose(Base):
    __tablename__ = "subscription_purposes"

    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscription_accounts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    purpose_id: Mapped[int] = mapped_column(
        ForeignKey("purposes.id", ondelete="CASCADE"),
        primary_key=True,
    )
