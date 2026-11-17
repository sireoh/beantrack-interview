from datetime import datetime
from typing import Any

from pydantic import Field, model_validator

from app.models.enums import WatchStatus
from app.schemas.common import ImdbId, MediaOut, ORMModel, RequestModel


class TvShowOut(MediaOut):
    """`title`/`image` are what this user should see: their personal override when custom
    display is on, otherwise the shared catalogue values (also given as catalog_*)."""

    episodes_count: int
    catalog_title: str
    catalog_image: str | None


class TvOverrideOut(ORMModel):
    custom_title: str | None
    custom_image: str | None


class EpisodeOut(ORMModel):
    id: int
    season: int
    number: int | None
    title: str
    image: str | None


class EpisodeMetadata(RequestModel):
    id: int
    season: int
    number: int | None
    title: str
    image: str | None


class TvListEntryOut(ORMModel):
    show: TvShowOut
    # The user's stored override (returned even while custom display is off), or null.
    override: TvOverrideOut | None
    # True when `override` is currently applied to show.title / show.image.
    override_active: bool
    status: WatchStatus
    current_episode: int
    current_episode_metadata: EpisodeMetadata | None
    added_at: datetime
    updated_at: datetime


class TvListOut(ORMModel):
    tvlist_id: str
    entries: list[TvListEntryOut]


class TvEpisodeData(RequestModel):
    id: int
    title: str
    image: str | None = None
    season: int
    number: int | None = None


class TvShowData(RequestModel):
    imdb: ImdbId
    tvmaze_id: int
    title: str
    image: str | None = None
    score: float | None = None


class TvListAddRequest(RequestModel):
    show: TvShowData
    status: WatchStatus = WatchStatus.PLANNED
    # Zero-based index into the separately cached episode list.
    current_episode: int = Field(default=0, ge=0)


class TvProgressRequest(RequestModel):
    set_to: int | None = Field(default=None, ge=0)
    delta: int | None = Field(default=None, ge=-1000, le=1000)
    current_episode_metadata: EpisodeMetadata

    @model_validator(mode="after")
    def _exactly_one_operation(self) -> "TvProgressRequest":
        if (self.set_to is None) == (self.delta is None):
            raise ValueError("Exactly one of set_to or delta is required")
        return self
