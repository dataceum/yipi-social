"""Comment models — threaded comments on a Post via a self-referential FK."""

from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
import sqlalchemy as sa

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.post import Post
    from app.models.like import Like

#########################################################
#                    COMMENT LAYER                       #
#########################################################


class CommentBase(SQLModel):
    content: str = Field(min_length=1, max_length=1000)


class CommentCreate(CommentBase):
    """
    parent_comment_id is optional — omit it for a top-level comment on the
    post, or supply an existing comment's id to reply to that comment.
    """

    parent_comment_id: Optional[int] = None


class CommentUpdate(SQLModel):
    content: str = Field(min_length=1, max_length=1000)


class Comment(CommentBase, table=True):
    __tablename__ = "comments"

    id: int = Field(default=None, primary_key=True)
    post_id: int = Field(foreign_key="posts.id", index=True, ondelete="CASCADE")
    author_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")

    # Self-referential FK for threading. Null = top-level comment on the post.
    # Deleting a parent comment cascades to its replies, at the DB level.
    parent_comment_id: Optional[int] = Field(
        default=None, foreign_key="comments.id", index=True, ondelete="CASCADE"
    )

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

    post: "Post" = Relationship(
        back_populates="comments",
        sa_relationship_kwargs={
            "foreign_keys": "[Comment.post_id]",
            "lazy": "selectin",
        },
    )
    author: "User" = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[Comment.author_id]",
            "lazy": "selectin",
        },
    )
    # Intentionally NOT eager-loaded (no lazy="selectin") — a popular comment
    # could have hundreds of replies, and selectin-loading the full tree on
    # every fetch doesn't scale. Replies are fetched via a dedicated,
    # paginated endpoint instead (e.g. GET /comments/{id}/replies).
    replies: List["Comment"] = Relationship(
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "foreign_keys": "[Comment.parent_comment_id]",
        },
    )
    # A comment can be liked (self-likes allowed — see like.py).
    likes: List["Like"] = Relationship(
        back_populates="comment",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "foreign_keys": "[Like.comment_id]",
            "lazy": "selectin",
        },
    )


##########################################################
# OUTGOING RESPONSE PAYLOAD DATA TRANSFER OBJECTS (DTOs) #
##########################################################


class CommentAuthorSummary(SQLModel):
    id: int
    username: str
    first_name: str
    last_name: str


class CommentResponse(CommentBase):
    id: int
    post_id: int
    parent_comment_id: Optional[int] = None
    author: CommentAuthorSummary
    reply_count: int = 0
    like_count: int = 0
    date_created: datetime
    date_modified: datetime


class CommentListResponse(SQLModel):
    total_count: int
    results: List[CommentResponse]
