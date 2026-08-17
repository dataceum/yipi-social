"""
Post models and schemas, following the same Base/Create/Update/table/Response
pattern established in user.py and profile.py.
"""

from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
import sqlalchemy as sa
from app.models.enums import PostStatus, MediaType

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.comment import Comment
    from app.models.like import Like
    from app.models.report import Report

#########################################################
#                     POST LAYER                        #
#########################################################


class PostBase(SQLModel):
    content: str = Field(min_length=1, max_length=2000)


class PostMediaBase(SQLModel):
    media_url: str
    media_type: MediaType = Field(
        sa_column=sa.Column(
            sa.Enum(MediaType, name="media_type_enum", create_type=False)
        )
    )


class PostMediaCreate(PostMediaBase):
    """A single attachment supplied inline at post-creation time."""


class PostMedia(PostMediaBase, table=True):
    """
    Modeled as its own table rather than an array column, so individual
    attachments can be ordered, queried, and moderated independently.
    """

    __tablename__ = "post_media"
    id: int = Field(default=None, primary_key=True)
    post_id: int = Field(foreign_key="posts.id", index=True, ondelete="CASCADE")
    display_order: int = Field(default=0)

    date_created: datetime = Field(
        sa_type=sa.DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    post: "Post" = Relationship(
        back_populates="media",
        sa_relationship_kwargs={
            "foreign_keys": "[PostMedia.post_id]",
            "lazy": "selectin",
        },
    )


class PostCreate(PostBase):
    """
    Accepts 1+ media attachments inline; the endpoint is responsible for
    fanning these into PostMedia rows atomically alongside the Post row.

    parent_post_id is optional — omit it for a standalone top-level post,
    or supply an existing post's id to reply into that post's thread.
    """

    media: List[PostMediaCreate] = Field(default_factory=list, max_length=10)
    parent_post_id: Optional[int] = None


class PostUpdate(SQLModel):
    """
    Media attachments are managed via separate add/remove endpoints rather
    than a full-payload PATCH — diffing a media list against existing rows
    is its own concern, distinct from editing text/status.
    """

    content: Optional[str] = None
    status: Optional[PostStatus] = None


class Post(PostBase, table=True):
    __tablename__ = "posts"

    id: int = Field(default=None, primary_key=True)
    author_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")

    # Self-referential FK for threading, mirroring Comment.parent_comment_id.
    # Null = top-level post. Deleting a parent post cascades to its replies,
    # at the DB level.
    parent_post_id: Optional[int] = Field(
        default=None, foreign_key="posts.id", index=True, ondelete="CASCADE"
    )

    status: PostStatus = Field(
        sa_column=sa.Column(
            sa.Enum(PostStatus, name="post_status_enum", create_type=False),
            nullable=False,
        ),
        default=PostStatus.PUBLISHED,
    )

    # Audit footprints
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

    author: "User" = Relationship(
        back_populates="posts",
        sa_relationship_kwargs={"foreign_keys": "[Post.author_id]", "lazy": "selectin"},
    )
    # Intentionally NOT eager-loaded (no lazy="selectin") — same reasoning as
    # Comment.replies: a heavily-replied-to post could have a large thread,
    # and selectin-loading the full tree on every fetch doesn't scale.
    # Replies are fetched via a dedicated, paginated endpoint instead
    # (e.g. GET /posts/{id}/replies).
    replies: List["Post"] = Relationship(
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "foreign_keys": "[Post.parent_post_id]",
        },
    )
    media: List["PostMedia"] = Relationship(
        back_populates="post",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "order_by": "PostMedia.display_order",
            "lazy": "selectin",
        },
    )
    comments: List["Comment"] = Relationship(
        back_populates="post",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "lazy": "selectin"},
    )
    # A post can be liked (self-likes allowed — see like.py).
    likes: List["Like"] = Relationship(
        back_populates="post",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "foreign_keys": "[Like.post_id]",
            "lazy": "selectin",
        },
    )
    # Intentionally NOT eager-loaded — a heavily-reported post shouldn't
    # inflate every normal fetch. Moderators pull these via a dedicated
    # endpoint (e.g. GET /posts/{id}/reports).
    reports: List["Report"] = Relationship(
        back_populates="post",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "foreign_keys": "[Report.post_id]",
        },
    )


##########################################################
# OUTGOING RESPONSE PAYLOAD DATA TRANSFER OBJECTS (DTOs) #
##########################################################


class PostMediaResponse(PostMediaBase):
    id: int
    display_order: int


class PostAuthorSummary(SQLModel):
    id: int
    username: str
    first_name: str
    last_name: str


class PostResponse(PostBase):
    id: int
    status: PostStatus
    author: PostAuthorSummary
    parent_post_id: Optional[int] = None
    media: List[PostMediaResponse] = []
    comment_count: int = 0
    reply_count: int = 0
    like_count: int = 0
    date_created: datetime
    date_modified: datetime


class PostListResponse(SQLModel):
    total_count: int
    results: List[PostResponse]
