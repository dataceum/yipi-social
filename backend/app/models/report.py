"""Report model — a user flagging a Post or a Room for not meeting
community standards. Mirrors Like's polymorphic-target pattern: a report
targets exactly one of {post, room}, enforced by a DB-level check
constraint, so moderation queries stay simple regardless of target type.

Unlike Like, a report carries a review workflow (status, resolution notes,
reviewing moderator) since someone has to act on it.
"""

from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship, UniqueConstraint
import sqlalchemy as sa
from app.models.enums import ReportReason, ReportStatus

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.post import Post
    from app.models.room import Room

#########################################################
#                    REPORT LAYER                        #
#########################################################


class ReportBase(SQLModel):
    reason: ReportReason
    details: Optional[str] = Field(default=None, max_length=1000)


class ReportCreate(ReportBase):
    """
    Empty target fields by design — same convention as LikeCreate: the
    reported target (post or room) is taken from the URL (e.g.
    POST /posts/{id}/reports or POST /rooms/{id}/reports) and the
    reporting user from the auth context, never from the request payload.
    """


class ReportUpdate(SQLModel):
    """Moderator-only: transition a report through its review workflow."""

    status: Optional[ReportStatus] = None
    resolution_notes: Optional[str] = Field(default=None, max_length=1000)


class Report(ReportBase, table=True):
    __tablename__ = "reports"
    __table_args__ = (
        # A user can report a given post/room more than once is undesirable —
        # one open report per (target, reporter) pair.
        UniqueConstraint("post_id", "reporter_id", name="uq_report_post_reporter"),
        UniqueConstraint("room_id", "reporter_id", name="uq_report_room_reporter"),
        sa.CheckConstraint(
            "(post_id IS NOT NULL AND room_id IS NULL) "
            "OR (post_id IS NULL AND room_id IS NOT NULL)",
            name="ck_report_exactly_one_target",
        ),
    )

    id: int = Field(default=None, primary_key=True)
    post_id: Optional[int] = Field(
        default=None, foreign_key="posts.id", index=True, ondelete="CASCADE"
    )
    room_id: Optional[int] = Field(
        default=None, foreign_key="rooms.id", index=True, ondelete="CASCADE"
    )
    reporter_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")

    status: ReportStatus = Field(
        sa_column=sa.Column(
            sa.Enum(ReportStatus, name="report_status_enum", create_type=False),
            nullable=False,
        ),
        default=ReportStatus.PENDING,
    )
    resolution_notes: Optional[str] = Field(default=None, max_length=1000)
    # The moderator who reviewed the report. Null while PENDING.
    reviewed_by: Optional[int] = Field(
        default=None, foreign_key="users.id", nullable=True
    )

    date_created: datetime = Field(
        sa_type=sa.DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    date_modified: datetime = Field(
        sa_type=sa.DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    post: Optional["Post"] = Relationship(
        back_populates="reports",
        sa_relationship_kwargs={
            "foreign_keys": "[Report.post_id]",
            "lazy": "selectin",
        },
    )
    room: Optional["Room"] = Relationship(
        back_populates="reports",
        sa_relationship_kwargs={
            "foreign_keys": "[Report.room_id]",
            "lazy": "selectin",
        },
    )
    reporter: "User" = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[Report.reporter_id]",
            "lazy": "selectin",
        },
    )


##########################################################
# OUTGOING RESPONSE PAYLOAD DATA TRANSFER OBJECTS (DTOs) #
##########################################################


class ReportReporterSummary(SQLModel):
    id: int
    username: str
    first_name: str
    last_name: str


class ReportResponse(ReportBase):
    id: int
    post_id: Optional[int] = None
    room_id: Optional[int] = None
    reporter: ReportReporterSummary
    status: ReportStatus
    resolution_notes: Optional[str] = None
    reviewed_by: Optional[int] = None
    date_created: datetime
    date_modified: datetime


class ReportListResponse(SQLModel):
    total_count: int
    results: List[ReportResponse]
