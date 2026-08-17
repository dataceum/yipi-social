"""Like model — a user's like on a post OR a comment. No update semantics;
a like is either present (created) or absent (deleted), never edited.

A like targets exactly one of {post, comment} — enforced by a DB-level
check constraint rather than two separate tables, so "who liked this" and
like-count queries stay simple regardless of target type.

Self-likes are intentionally unrestricted: a user liking their own post or
comment is valid and is not blocked at the model layer.
"""

from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship, UniqueConstraint
import sqlalchemy as sa

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.comment import Comment

#########################################################
#                     LIKE LAYER                         #
#########################################################


class LikeCreate(SQLModel):
    """
    Empty body by design — the like's target (post or comment) is taken
    from the URL (e.g. POST /posts/{id}/likes or POST /comments/{id}/likes)
    and the liking user is taken from the auth context, never from the
    request payload.
    """


class Like(SQLModel, table=True):
    __tablename__ = "likes"
    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="uq_like_post_user"),
        UniqueConstraint("comment_id", "user_id", name="uq_like_comment_user"),
        sa.CheckConstraint(
            "(post_id IS NOT NULL AND comment_id IS NULL) "
            "OR (post_id IS NULL AND comment_id IS NOT NULL)",
            name="ck_like_exactly_one_target",
        ),
    )

    id: int = Field(default=None, primary_key=True)
    post_id: Optional[int] = Field(
        default=None, foreign_key="posts.id", index=True, ondelete="CASCADE"
    )
    comment_id: Optional[int] = Field(
        default=None, foreign_key="comments.id", index=True, ondelete="CASCADE"
    )
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")

    date_created: datetime = Field(
        sa_type=sa.DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    post: Optional["Post"] = Relationship(
        back_populates="likes",
        sa_relationship_kwargs={"foreign_keys": "[Like.post_id]", "lazy": "selectin"},
    )
    comment: Optional["Comment"] = Relationship(
        back_populates="likes",
        sa_relationship_kwargs={
            "foreign_keys": "[Like.comment_id]",
            "lazy": "selectin",
        },
    )


##########################################################
# OUTGOING RESPONSE PAYLOAD DATA TRANSFER OBJECTS (DTOs) #
##########################################################


class LikeAuthorSummary(SQLModel):
    id: int
    username: str
    first_name: str
    last_name: str


class LikeResponse(SQLModel):
    id: int
    post_id: Optional[int] = None
    comment_id: Optional[int] = None
    user: LikeAuthorSummary
    date_created: datetime


class LikeListResponse(SQLModel):
    total_count: int
    results: List[LikeResponse]
