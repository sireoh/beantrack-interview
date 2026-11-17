"""Catalogue corrections (shared, admin-reviewed) and personal display overrides.

Two separate mechanisms, kept apart on purpose:

- A **correction** proposes a new title/image for the shared show. It changes nothing for
  anyone, its submitter included, until an admin approves it; approval writes the proposed
  fields onto `tvshows`.
- An **override** is the user's own title/image for a show on their list. It applies at once,
  only to them, and only while `users.custom_display_enabled` is on.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.db.types import utcnow
from app.models import CorrectionStatus, ShowCorrection, TvList, TvOverride, TvShow, User, UserTvShow
from app.repositories import corrections as corrections_repo
from app.repositories import media as media_repo
from app.repositories import tvlists as tvlists_repo
from app.schemas.corrections import (
    AdminCorrectionOut,
    CorrectionCreateRequest,
    CorrectionOut,
    OverrideRequest,
)
from app.schemas.tvlist import (
    EpisodeMetadata,
    TvListEntryOut,
    TvListOut,
    TvOverrideOut,
    TvShowOut,
)
from app.schemas.user import discord_avatar_url
from app.services.lists import TV_NOT_FOUND

SHOW_NOT_FOUND = "TV show not found"
CORRECTION_NOT_FOUND = "Correction not found"
NOT_PENDING = "Only a pending correction can be reviewed"


def _require_show(db: Session, imdb_id: str) -> TvShow:
    show = media_repo.get_tvshow(db, imdb_id)
    if show is None:
        raise NotFoundError(SHOW_NOT_FOUND)
    return show


def _correction_out(correction: ShowCorrection, show: TvShow) -> CorrectionOut:
    return CorrectionOut(
        id=correction.id,
        imdb_id=correction.imdb_id,
        status=correction.status,
        current_title=show.title,
        current_image=show.image,
        new_title=correction.new_title,
        new_image=correction.new_image,
        created_at=correction.created_at,
        reviewed_at=correction.reviewed_at,
    )


def _admin_out(correction: ShowCorrection, show: TvShow, submitter: User) -> AdminCorrectionOut:
    return AdminCorrectionOut(
        **_correction_out(correction, show).model_dump(),
        discord_id=submitter.discord_id,
        username=submitter.username,
        avatar_url=discord_avatar_url(submitter.discord_id, submitter.avatar),
        reviewed_by=correction.reviewed_by,
    )


# --- submitting -----------------------------------------------------------------------


def submit_correction(
    db: Session, *, user: User, request: CorrectionCreateRequest
) -> tuple[CorrectionOut, bool]:
    """Create a pending correction, or replace the user's existing pending one for the show.

    Returns (correction, created). Second correction rule: while a user has a pending
    correction for a show, submitting again overwrites that row in place (same id, both
    proposed fields replaced, created_at refreshed) instead of adding another.
    """
    show = _require_show(db, request.imdb_id)
    pending = corrections_repo.get_pending_for(
        db, submitted_by=user.discord_id, imdb_id=show.imdb
    )
    if pending is None:
        try:
            pending = corrections_repo.add(
                db,
                ShowCorrection(
                    imdb_id=show.imdb,
                    submitted_by=user.discord_id,
                    new_title=request.new_title,
                    new_image=request.new_image,
                    status=CorrectionStatus.PENDING,
                    created_at=utcnow(),
                ),
            )
            db.commit()
            return _correction_out(pending, show), True
        except IntegrityError:
            # A concurrent submit won the partial unique index; fall through and update it.
            db.rollback()
            pending = corrections_repo.get_pending_for(
                db, submitted_by=user.discord_id, imdb_id=show.imdb
            )
            if pending is None:
                raise

    pending.new_title = request.new_title
    pending.new_image = request.new_image
    pending.created_at = utcnow()
    db.commit()
    return _correction_out(pending, show), False


def list_my_corrections(db: Session, user: User) -> list[CorrectionOut]:
    rows = corrections_repo.list_with_show(db, submitted_by=user.discord_id)
    return [_correction_out(correction, show) for correction, show in rows]


# --- reviewing (admin) ----------------------------------------------------------------


def list_for_review(db: Session, status: CorrectionStatus | None) -> list[AdminCorrectionOut]:
    rows = corrections_repo.list_for_review(db, status=status)
    return [_admin_out(correction, show, user) for correction, show, user in rows]


def _review(
    db: Session, *, admin: User, correction_id: int, status: CorrectionStatus
) -> AdminCorrectionOut:
    correction = corrections_repo.get(db, correction_id)
    if correction is None:
        raise NotFoundError(CORRECTION_NOT_FOUND)
    if not corrections_repo.mark_reviewed(
        db,
        correction_id,
        status=status,
        reviewed_by=admin.discord_id,
        reviewed_at=utcnow(),
    ):
        db.rollback()
        raise ConflictError(NOT_PENDING)

    show = _require_show(db, correction.imdb_id)
    if status == CorrectionStatus.APPROVED:
        # Only the fields the correction actually sets are copied onto the shared show.
        if correction.new_title is not None:
            show.title = correction.new_title
        if correction.new_image is not None:
            show.image = correction.new_image
    db.commit()
    db.refresh(correction)
    submitter = db.get(User, correction.submitted_by)
    assert submitter is not None
    return _admin_out(correction, show, submitter)


def approve_correction(db: Session, *, admin: User, correction_id: int) -> AdminCorrectionOut:
    return _review(db, admin=admin, correction_id=correction_id, status=CorrectionStatus.APPROVED)


def reject_correction(db: Session, *, admin: User, correction_id: int) -> AdminCorrectionOut:
    return _review(db, admin=admin, correction_id=correction_id, status=CorrectionStatus.REJECTED)


# --- personal overrides ---------------------------------------------------------------


def _require_entry(db: Session, user: User, imdb_id: str) -> UserTvShow:
    _require_show(db, imdb_id)
    entry = tvlists_repo.get_entry(db, user.tvlist.tvlist_id, imdb_id)
    if entry is None:
        raise NotFoundError(TV_NOT_FOUND)
    return entry


def set_override(
    db: Session, *, user: User, imdb_id: str, request: OverrideRequest
) -> TvListEntryOut:
    """Set (replace) the user's own title/image for a show on their list."""
    entry = _require_entry(db, user, imdb_id)
    override = corrections_repo.upsert_override(
        db,
        discord_id=user.discord_id,
        imdb_id=imdb_id,
        custom_title=request.custom_title,
        custom_image=request.custom_image,
    )
    db.commit()
    return entry_out(entry, user=user, override=override)


def remove_override(db: Session, *, user: User, imdb_id: str) -> None:
    """Remove the user's override; a no-op if there is none."""
    _require_entry(db, user, imdb_id)
    override = corrections_repo.get_override(db, discord_id=user.discord_id, imdb_id=imdb_id)
    if override is not None:
        corrections_repo.delete_override(db, override)
        db.commit()


def set_custom_display(db: Session, *, user: User, enabled: bool) -> bool:
    user.custom_display_enabled = enabled
    db.commit()
    return user.custom_display_enabled


# --- building what the user sees ------------------------------------------------------


def entry_out(entry: UserTvShow, *, user: User, override: TvOverride | None) -> TvListEntryOut:
    """A list entry with the title/image this user should see.

    Starts from the shared show; if custom display is on and the user has an override, its
    non-null fields replace the shared ones.
    """
    show = entry.show
    active = override is not None and user.custom_display_enabled
    title, image = show.title, show.image
    if active and override is not None:
        title = override.custom_title if override.custom_title is not None else title
        image = override.custom_image if override.custom_image is not None else image
    metadata = entry.current_episode_metadata
    return TvListEntryOut(
        show=TvShowOut(
            imdb=show.imdb,
            title=title,
            image=image,
            score=show.score,
            episodes_count=show.episodes_count,
            catalog_title=show.title,
            catalog_image=show.image,
        ),
        override=TvOverrideOut.model_validate(override) if override is not None else None,
        override_active=active,
        status=entry.status,
        current_episode=entry.current_episode,
        current_episode_metadata=(
            EpisodeMetadata.model_validate(metadata) if metadata is not None else None
        ),
        rating=entry.rating,
        added_at=entry.added_at,
        updated_at=entry.updated_at,
    )


def tv_entry_out(db: Session, user: User, entry: UserTvShow) -> TvListEntryOut:
    override = corrections_repo.get_override(db, discord_id=user.discord_id, imdb_id=entry.imdb)
    return entry_out(entry, user=user, override=override)


def tvlist_out(db: Session, user: User, tvlist: TvList) -> TvListOut:
    overrides = corrections_repo.overrides_for(
        db, user.discord_id, (entry.imdb for entry in tvlist.entries)
    )
    return TvListOut(
        tvlist_id=tvlist.tvlist_id,
        entries=[
            entry_out(entry, user=user, override=overrides.get(entry.imdb))
            for entry in tvlist.entries
        ],
    )
