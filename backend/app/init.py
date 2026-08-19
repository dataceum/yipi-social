"""
Central model registry.

SQLAlchemy only resolves a string-based relationship target (e.g.
`Relationship(sa_relationship_kwargs={"foreign_keys": "[...]"})` or a
forward-ref type hint like `"Comment"`) if that class has actually been
*imported* somewhere before `configure_mappers()` runs — a `TYPE_CHECKING`
import doesn't count, since it never executes at runtime.

Individual model files intentionally only import each other under
`TYPE_CHECKING` (to avoid circular imports), so nothing guarantees they're
all loaded together. Importing this package once, at app startup — before
the engine/session is used — is what actually registers every table class
with SQLAlchemy's declarative registry in one place, regardless of which
module happened to get imported first.

Import this in app startup (e.g. `app/main.py`, or wherever
`get_async_session` / the engine is first constructed) via:

    import app.models  # noqa: F401

or equivalently `from app.models import *` if your entrypoint prefers that.
"""

from app.models.user import User  # noqa: F401
from app.models.profile import Profile  # noqa: F401
from app.models.token import Token  # noqa: F401
from app.models.post import Post, PostMedia  # noqa: F401
from app.models.comment import Comment  # noqa: F401
from app.models.like import Like  # noqa: F401
from app.models.room import Room, RoomMember, RoomMessage  # noqa: F401
from app.models.report import Report  # noqa: F401
from app.models.team import Team, Agent  # noqa: F401
from app.models.call import Call  # noqa: F401
from app.models.api_key import APIKey  # noqa: F401

__all__ = [
    "User",
    "Profile",
    "Token",
    "Post",
    "PostMedia",
    "Comment",
    "Like",
    "Room",
    "RoomMember",
    "RoomMessage",
    "Report",
    "Team",
    "Agent",
    "Call",
    "APIKey",
]
