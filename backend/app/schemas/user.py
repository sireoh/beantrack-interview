from datetime import datetime

from pydantic import computed_field

from app.models.enums import Theme, UserRole
from app.schemas.common import ORMModel, RequestModel


class UserOut(ORMModel):
    discord_id: str
    username: str
    avatar: str | None
    created_at: datetime
    last_login: datetime
    role: UserRole
    theme: Theme | None
    custom_display_enabled: bool

    @computed_field  # type: ignore[prop-decorator]
    @property
    def avatar_url(self) -> str | None:
        return discord_avatar_url(self.discord_id, self.avatar)


def discord_avatar_url(discord_id: str, avatar: str | None) -> str | None:
    if avatar is None:
        return None
    return f"https://cdn.discordapp.com/avatars/{discord_id}/{avatar}.png"


class ThemeUpdateRequest(RequestModel):
    theme: Theme
