"""Catalogue corrections (shared, need admin approval) and personal display overrides.

The two are deliberately separate tables: a pending correction never changes what anyone
sees, while an override changes only its owner's view and takes effect at once.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime, utcnow
from app.models.enums import CorrectionStatus, correction_status_column_type

TITLE_MAX_LENGTH = 255
IMAGE_MAX_LENGTH = 512


class ShowCorrection(Base):
    """A proposed new title and/or image for a shared TV show."""

    __tablename__ = "show_corrections"
    __table_args__ = (
        CheckConstraint(
            "new_title IS NOT NULL OR new_image IS NOT NULL", name="title_or_image"
        ),
        # At most one pending correction per user per show (the "second correction rule").
        Index(
            "uq_show_corrections_one_pending",
            "submitted_by",
            "imdb_id",
            unique=True,
            sqlite_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    imdb_id: Mapped[str] = mapped_column(
        ForeignKey("tvshows.imdb", ondelete="CASCADE"), index=True
    )
    submitted_by: Mapped[str] = mapped_column(
        ForeignKey("users.discord_id", ondelete="CASCADE"), index=True
    )
    new_title: Mapped[str | None] = mapped_column(String(TITLE_MAX_LENGTH))
    new_image: Mapped[str | None] = mapped_column(String(IMAGE_MAX_LENGTH))
    status: Mapped[CorrectionStatus] = mapped_column(
        correction_status_column_type(), default=CorrectionStatus.PENDING, index=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    reviewed_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.discord_id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class TvOverride(Base):
    """A user's own title/image for a show. Null fields fall back to the shared value."""

    __tablename__ = "tv_overrides"

    discord_id: Mapped[str] = mapped_column(
        ForeignKey("users.discord_id", ondelete="CASCADE"), primary_key=True
    )
    imdb_id: Mapped[str] = mapped_column(
        ForeignKey("tvshows.imdb", ondelete="CASCADE"), primary_key=True
    )
    custom_title: Mapped[str | None] = mapped_column(String(TITLE_MAX_LENGTH))
    custom_image: Mapped[str | None] = mapped_column(String(IMAGE_MAX_LENGTH))
