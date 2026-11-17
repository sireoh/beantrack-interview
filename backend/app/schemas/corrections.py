"""Catalogue corrections, personal overrides and the custom-display setting."""

from datetime import datetime
from typing import Annotated, Self

from pydantic import StringConstraints, model_validator

from app.models.corrections import IMAGE_MAX_LENGTH, TITLE_MAX_LENGTH
from app.models.enums import CorrectionStatus
from app.schemas.common import ORMModel, RequestModel, StrictImdbId

# Titles are stored exactly as typed (no trimming), but must contain something visible.
Title = Annotated[str, StringConstraints(min_length=1, max_length=TITLE_MAX_LENGTH, pattern=r"\S")]
# A plain http(s) URL for now; there is no image upload. Rejects javascript:, data: etc.
ImageUrl = Annotated[
    str, StringConstraints(max_length=IMAGE_MAX_LENGTH, pattern=r"^https?://[^\s]+$")
]


class CorrectionCreateRequest(RequestModel):
    imdb_id: StrictImdbId
    new_title: Title | None = None
    new_image: ImageUrl | None = None

    @model_validator(mode="after")
    def _title_or_image(self) -> Self:
        if self.new_title is None and self.new_image is None:
            raise ValueError("At least one of new_title or new_image is required")
        return self


class CorrectionOut(ORMModel):
    """A correction as its submitter sees it (GET /corrections/mine, POST /corrections)."""

    id: int
    imdb_id: str
    status: CorrectionStatus
    # The shared show as it is now, to show next to the proposal.
    current_title: str
    current_image: str | None
    new_title: str | None
    new_image: str | None
    created_at: datetime
    reviewed_at: datetime | None


class AdminCorrectionOut(CorrectionOut):
    """A correction in the admin review queue, with who submitted it."""

    discord_id: str
    username: str
    avatar_url: str | None
    reviewed_by: str | None


class OverrideRequest(RequestModel):
    custom_title: Title | None = None
    custom_image: ImageUrl | None = None

    @model_validator(mode="after")
    def _title_or_image(self) -> Self:
        if self.custom_title is None and self.custom_image is None:
            raise ValueError(
                "At least one of custom_title or custom_image is required; "
                "use DELETE to remove the override"
            )
        return self


class CustomDisplayOut(ORMModel):
    enabled: bool


class CustomDisplayRequest(RequestModel):
    enabled: bool
