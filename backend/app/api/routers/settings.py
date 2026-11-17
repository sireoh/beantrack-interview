"""Per-user settings."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.corrections import CustomDisplayOut, CustomDisplayRequest
from app.services import corrections as corrections_service

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/custom-display", response_model=CustomDisplayOut)
def get_custom_display(user: CurrentUser) -> CustomDisplayOut:
    """Whether your personal title/image overrides are shown in your list."""
    return CustomDisplayOut(enabled=user.custom_display_enabled)


@router.put("/custom-display", response_model=CustomDisplayOut)
def set_custom_display(
    body: CustomDisplayRequest, user: CurrentUser, db: DbSession
) -> CustomDisplayOut:
    enabled = corrections_service.set_custom_display(db, user=user, enabled=body.enabled)
    return CustomDisplayOut(enabled=enabled)
