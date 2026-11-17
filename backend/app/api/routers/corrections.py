"""Catalogue corrections: users propose, admins approve or reject."""

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import AdminUser, CurrentUser, DbSession, require_admin
from app.models import CorrectionStatus
from app.schemas.corrections import AdminCorrectionOut, CorrectionCreateRequest, CorrectionOut
from app.services import corrections as corrections_service

router = APIRouter(prefix="/corrections", tags=["corrections"])
admin_router = APIRouter(
    prefix="/admin/corrections", tags=["admin"], dependencies=[Depends(require_admin)]
)


@router.post(
    "",
    response_model=CorrectionOut,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "Replaced your existing pending correction for this show"}},
)
def submit_correction(
    body: CorrectionCreateRequest, response: Response, user: CurrentUser, db: DbSession
) -> CorrectionOut:
    """Propose a new title and/or image for a shared show. Nothing changes until an admin
    approves it. A second submit while one is pending updates it in place (200)."""
    correction, created = corrections_service.submit_correction(db, user=user, request=body)
    if not created:
        response.status_code = status.HTTP_200_OK
    return correction


@router.get("/mine", response_model=list[CorrectionOut])
def my_corrections(user: CurrentUser, db: DbSession) -> list[CorrectionOut]:
    """Your own corrections in every status, newest first."""
    return corrections_service.list_my_corrections(db, user)


@admin_router.get("", response_model=list[AdminCorrectionOut])
def list_corrections(
    db: DbSession, status: CorrectionStatus | None = None
) -> list[AdminCorrectionOut]:
    """Corrections to review, oldest first. Filter with ?status=pending|approved|rejected."""
    return corrections_service.list_for_review(db, status)


@admin_router.patch("/{correction_id}/approve", response_model=AdminCorrectionOut)
def approve_correction(correction_id: int, admin: AdminUser, db: DbSession) -> AdminCorrectionOut:
    """Approve a pending correction and copy its fields onto the shared show."""
    return corrections_service.approve_correction(db, admin=admin, correction_id=correction_id)


@admin_router.patch("/{correction_id}/reject", response_model=AdminCorrectionOut)
def reject_correction(correction_id: int, admin: AdminUser, db: DbSession) -> AdminCorrectionOut:
    """Reject a pending correction; the show is unchanged."""
    return corrections_service.reject_correction(db, admin=admin, correction_id=correction_id)
