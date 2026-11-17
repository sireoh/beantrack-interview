"""Queries for catalogue corrections and personal overrides.

Everything goes through SQLAlchemy expressions, so values are always bound parameters.
"""

from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any, cast

from sqlalchemy import CursorResult, Row, select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from app.models import CorrectionStatus, ShowCorrection, TvOverride, TvShow, User


# --- corrections ----------------------------------------------------------------------


def get(db: Session, correction_id: int) -> ShowCorrection | None:
    return db.get(ShowCorrection, correction_id)


def get_pending_for(db: Session, *, submitted_by: str, imdb_id: str) -> ShowCorrection | None:
    stmt = select(ShowCorrection).where(
        ShowCorrection.submitted_by == submitted_by,
        ShowCorrection.imdb_id == imdb_id,
        ShowCorrection.status == CorrectionStatus.PENDING,
    )
    return db.scalars(stmt).one_or_none()


def add(db: Session, correction: ShowCorrection) -> ShowCorrection:
    db.add(correction)
    db.flush()
    return correction


def list_with_show(
    db: Session, *, submitted_by: str
) -> Sequence[Row[ShowCorrection, TvShow]]:
    """A user's own corrections (any status), newest first, each with its shared show."""
    stmt = (
        select(ShowCorrection, TvShow)
        .join(TvShow, TvShow.imdb == ShowCorrection.imdb_id)
        .where(ShowCorrection.submitted_by == submitted_by)
        .order_by(ShowCorrection.created_at.desc(), ShowCorrection.id.desc())
    )
    return db.execute(stmt).all()


def list_for_review(
    db: Session, *, status: CorrectionStatus | None
) -> Sequence[Row[ShowCorrection, TvShow, User]]:
    """Corrections with their show and submitter, oldest first (a review queue)."""
    stmt = (
        select(ShowCorrection, TvShow, User)
        .join(TvShow, TvShow.imdb == ShowCorrection.imdb_id)
        .join(User, User.discord_id == ShowCorrection.submitted_by)
        .order_by(ShowCorrection.created_at, ShowCorrection.id)
    )
    if status is not None:
        stmt = stmt.where(ShowCorrection.status == status)
    return db.execute(stmt).all()


def mark_reviewed(
    db: Session,
    correction_id: int,
    *,
    status: CorrectionStatus,
    reviewed_by: str,
    reviewed_at: datetime,
) -> bool:
    """Move a *pending* correction to `status`. Returns False if it was no longer pending.

    A single conditional UPDATE, so two admins reviewing at once can't both succeed.
    """
    stmt = (
        update(ShowCorrection)
        .where(
            ShowCorrection.id == correction_id,
            ShowCorrection.status == CorrectionStatus.PENDING,
        )
        .values(status=status, reviewed_by=reviewed_by, reviewed_at=reviewed_at)
        .execution_options(synchronize_session="fetch")
    )
    result = cast(CursorResult[Any], db.execute(stmt))
    return result.rowcount == 1


# --- personal overrides ---------------------------------------------------------------


def get_override(db: Session, *, discord_id: str, imdb_id: str) -> TvOverride | None:
    return db.get(TvOverride, (discord_id, imdb_id))


def overrides_for(db: Session, discord_id: str, imdb_ids: Iterable[str]) -> dict[str, TvOverride]:
    ids = list(imdb_ids)
    if not ids:
        return {}
    stmt = select(TvOverride).where(
        TvOverride.discord_id == discord_id, TvOverride.imdb_id.in_(ids)
    )
    return {row.imdb_id: row for row in db.scalars(stmt)}


def delete_override(db: Session, override: TvOverride) -> None:
    db.delete(override)


def upsert_override(
    db: Session,
    *,
    discord_id: str,
    imdb_id: str,
    custom_title: str | None,
    custom_image: str | None,
) -> TvOverride:
    """Insert or replace the user's override (both fields are replaced)."""
    stmt = (
        insert(TvOverride)
        .values(
            discord_id=discord_id,
            imdb_id=imdb_id,
            custom_title=custom_title,
            custom_image=custom_image,
        )
        .on_conflict_do_update(
            index_elements=[TvOverride.discord_id, TvOverride.imdb_id],
            set_={"custom_title": custom_title, "custom_image": custom_image},
        )
    )
    db.execute(stmt)
    override = db.get(TvOverride, (discord_id, imdb_id), populate_existing=True)
    assert override is not None
    return override
