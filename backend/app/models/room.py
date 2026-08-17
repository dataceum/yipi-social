"""
Room models and schemas. A Room is either a live audio/video streaming
session or a private chat thread (1:1 or group), selected via `room_type`.

Both room types share the same participant model (RoomMember, with a role
and live-presence flags) and the same message thread (RoomMessage) — a
CHAT room's "conversation" and a LIVE room's "in-room chat" are the same
underlying table, distinguished only by which room they belong to.
"""

from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship, UniqueConstraint
import sqlalchemy as sa
from app.models.enums import RoomRole, RoomType, RoomStatus

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.report import Report

#########################################################
#                     ROOM LAYER                        #
#########################################################


class RoomBase(SQLModel):
    room_type: RoomType
    # Optional: private 1:1 chat threads are typically unnamed (the UI
    # derives a label from the other participant); named group chats and
    # live rooms will normally set this.
    name: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    room_picture_url: Optional[str] = None


class RoomCreate(RoomBase):
    """
    participant_ids seeds the room's membership at creation time (e.g. the
    other party in a 1:1 chat, or co-hosts/invitees for a live room). The
    creator is enrolled automatically as OWNER and does not need to be
    included here.
    """

    participant_ids: List[int] = Field(default_factory=list)


class RoomUpdate(SQLModel):
    """
    status is host/owner-only in practice (scheduled -> live -> ended) and
    only meaningful for LIVE_AUDIO / LIVE_VIDEO rooms.
    """

    name: Optional[str] = None
    description: Optional[str] = None
    room_picture_url: Optional[str] = None
    status: Optional[RoomStatus] = None


class Room(RoomBase, table=True):
    __tablename__ = "rooms"

    id: int = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")

    # Live-session state. Null/unused for CHAT rooms.
    status: Optional[RoomStatus] = Field(
        sa_column=sa.Column(
            sa.Enum(RoomStatus, name="room_status_enum", create_type=False),
            nullable=True,
        ),
    )
    # Playback/ingest endpoint for LIVE_AUDIO / LIVE_VIDEO (e.g. an
    # RTMP/HLS URL). Null for CHAT rooms.
    stream_url: Optional[str] = None
    scheduled_start: Optional[datetime] = Field(
        default=None, sa_type=sa.DateTime(timezone=True)
    )
    started_at: Optional[datetime] = Field(
        default=None, sa_type=sa.DateTime(timezone=True)
    )
    ended_at: Optional[datetime] = Field(
        default=None, sa_type=sa.DateTime(timezone=True)
    )

    # Moderation flag, set when a report against this room is filed (see
    # report.py) and cleared if the report is later dismissed. Kept as its
    # own boolean rather than folded into `status`, since `status` is
    # live-session state that's meaningless for CHAT rooms — suspension
    # needs to apply to every room type.
    is_suspended: bool = Field(default=False)

    date_created: datetime = Field(
        sa_type=sa.DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    date_modified: datetime = Field(
        sa_type=sa.DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    modified_by: Optional[int] = Field(
        default=None, foreign_key="users.id", nullable=True
    )

    owner: "User" = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[Room.owner_id]",
            "lazy": "selectin",
        },
    )
    members: List["RoomMember"] = Relationship(
        back_populates="room",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "lazy": "selectin",
        },
    )
    # Intentionally NOT eager-loaded — a chat thread's or a live room's
    # history can be long; fetched via a dedicated, paginated endpoint
    # instead (e.g. GET /rooms/{id}/messages), same reasoning applied to
    # Comment.replies / Post.replies.
    messages: List["RoomMessage"] = Relationship(
        back_populates="room",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    # Intentionally NOT eager-loaded — same reasoning as Post.reports.
    # Moderators pull these via a dedicated endpoint
    # (e.g. GET /rooms/{id}/reports).
    reports: List["Report"] = Relationship(
        back_populates="room",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "foreign_keys": "[Report.room_id]",
        },
    )


class RoomMember(SQLModel, table=True):
    """
    Join table between User and Room, carrying a per-room role plus
    live-presence flags that only apply to LIVE_AUDIO / LIVE_VIDEO rooms
    (ignored for CHAT rooms).
    """

    __tablename__ = "room_members"
    __table_args__ = (
        UniqueConstraint("room_id", "user_id", name="uq_room_member_room_user"),
    )

    id: int = Field(default=None, primary_key=True)
    room_id: int = Field(foreign_key="rooms.id", index=True, ondelete="CASCADE")
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    role: RoomRole = Field(
        sa_column=sa.Column(
            sa.Enum(RoomRole, name="room_role_enum", create_type=False),
            nullable=False,
        ),
        default=RoomRole.MEMBER,
    )
    # Live-room presence — irrelevant for CHAT rooms.
    is_speaker: bool = Field(default=False)
    is_muted: bool = Field(default=False)

    date_joined: datetime = Field(
        sa_type=sa.DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    date_left: Optional[datetime] = Field(
        default=None, sa_type=sa.DateTime(timezone=True)
    )

    room: "Room" = Relationship(
        back_populates="members",
        sa_relationship_kwargs={
            "foreign_keys": "[RoomMember.room_id]",
            "lazy": "selectin",
        },
    )
    user: "User" = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[RoomMember.user_id]",
            "lazy": "selectin",
        },
    )


class RoomMessageBase(SQLModel):
    content: str = Field(min_length=1, max_length=2000)


class RoomMessageCreate(RoomMessageBase):
    pass


class RoomMessage(RoomMessageBase, table=True):
    """
    A single message in a room's thread — doubles as a private-chat message
    (CHAT rooms) and in-room chat during a live session (LIVE_AUDIO /
    LIVE_VIDEO rooms).
    """

    __tablename__ = "room_messages"

    id: int = Field(default=None, primary_key=True)
    room_id: int = Field(foreign_key="rooms.id", index=True, ondelete="CASCADE")
    author_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")

    date_created: datetime = Field(
        sa_type=sa.DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    date_modified: datetime = Field(
        sa_type=sa.DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    room: "Room" = Relationship(
        back_populates="messages",
        sa_relationship_kwargs={
            "foreign_keys": "[RoomMessage.room_id]",
            "lazy": "selectin",
        },
    )
    author: "User" = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[RoomMessage.author_id]",
            "lazy": "selectin",
        },
    )


##########################################################
# OUTGOING RESPONSE PAYLOAD DATA TRANSFER OBJECTS (DTOs) #
##########################################################


class RoomMemberSummary(SQLModel):
    id: int
    username: str
    first_name: str
    last_name: str


class RoomMemberResponse(SQLModel):
    id: int
    room_id: int
    user: RoomMemberSummary
    role: RoomRole
    is_speaker: bool
    is_muted: bool
    date_joined: datetime
    date_left: Optional[datetime] = None


class RoomMessageResponse(RoomMessageBase):
    id: int
    room_id: int
    author: RoomMemberSummary
    date_created: datetime
    date_modified: datetime


class RoomResponse(RoomBase):
    id: int
    owner_id: int
    status: Optional[RoomStatus] = None
    stream_url: Optional[str] = None
    scheduled_start: Optional[datetime] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    is_suspended: bool = False
    member_count: int = 0
    date_created: datetime
    date_modified: datetime
    modified_by: Optional[int] = None


class RoomListResponse(SQLModel):
    total_count: int
    results: List[RoomResponse]


class RoomMemberListResponse(SQLModel):
    total_count: int
    results: List[RoomMemberResponse]


class RoomMessageListResponse(SQLModel):
    total_count: int
    results: List[RoomMessageResponse]
