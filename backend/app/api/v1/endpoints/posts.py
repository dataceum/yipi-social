###########################################################################################
# This script defines the post endpoints.
###########################################################################################

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_async_session
from app.core.security import get_current_user
from app.models.user import User
from app.models.enums import UserRole, PostStatus
from app.models.post import (
    Post,
    PostMedia,
    PostCreate,
    PostUpdate,
    PostResponse,
    PostListResponse,
    PostAuthorSummary,
    PostMediaResponse,
)

posts_router = APIRouter(prefix="/posts", tags=["Posts"])

# Statuses hidden from anyone who isn't the author or a reviewer.
_HIDDEN_STATUSES = {PostStatus.DELETED, PostStatus.SUSPENDED}


async def _reply_count(db: AsyncSession, post_id: int) -> int:
    return (
        await db.exec(select(func.count(Post.id)).where(Post.parent_post_id == post_id))
    ).one()


async def _to_response(db: AsyncSession, post: Post) -> PostResponse:
    """Builds a PostResponse, filling in the counts that aren't eager-loaded
    on the model (comments/likes are selectin-loaded; replies aren't)."""
    return PostResponse(
        id=post.id,
        content=post.content,
        status=post.status,
        author=PostAuthorSummary.model_validate(post.author),
        parent_post_id=post.parent_post_id,
        media=[PostMediaResponse.model_validate(m) for m in post.media],
        comment_count=len(post.comments),
        reply_count=await _reply_count(db, post.id),
        like_count=len(post.likes),
        date_created=post.date_created,
        date_modified=post.date_modified,
    )


def _is_reviewer(user: User) -> bool:
    return user.role in {UserRole.ADMIN, UserRole.MODERATOR}


def _visible(post: Post, current_user: User) -> bool:
    if post.status not in _HIDDEN_STATUSES:
        return True
    return _is_reviewer(current_user) or post.author_id == current_user.id


#############################################
#                CREATE POST                #
#############################################
@posts_router.post(
    "",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a post, optionally as a reply to another post",
)
async def create_post(
    payload: PostCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> PostResponse:
    """Create a new post for the current user, with 0+ inline media attachments.

    Supplying `parent_post_id` threads this post as a reply. The parent must
    exist and be visible to the caller; replying to a suspended/deleted/
    invisible post is rejected.
    """
    if payload.parent_post_id is not None:
        parent = await db.get(Post, payload.parent_post_id)
        if not parent or not _visible(parent, current_user):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent post not found.",
            )

    post = Post(
        content=payload.content,
        author_id=current_user.id,
        parent_post_id=payload.parent_post_id,
    )
    db.add(post)

    try:
        await db.flush()  # assign post.id for the media rows below

        for order, media_item in enumerate(payload.media):
            db.add(
                PostMedia(
                    post_id=post.id,
                    media_url=media_item.media_url,
                    media_type=media_item.media_type,
                    display_order=order,
                )
            )

        await db.commit()
        await db.refresh(post)
    except Exception:
        await db.rollback()
        raise

    return await _to_response(db, post)


#############################################
#                 LIST POSTS                #
#############################################
@posts_router.get(
    "",
    response_model=PostListResponse,
    summary="List top-level posts, optionally filtered by author",
)
async def list_posts(
    author_id: int | None = Query(None, description="Filter to one author's posts"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> PostListResponse:
    """List top-level (non-reply) posts, newest first. Suspended/deleted
    posts are excluded unless the caller is a reviewer or the author."""
    offset_delta = (page - 1) * limit
    filters = [Post.parent_post_id.is_(None)]

    if author_id is not None:
        filters.append(Post.author_id == author_id)

    if not _is_reviewer(current_user):
        filters.append(
            Post.status.not_in(_HIDDEN_STATUSES) | (Post.author_id == current_user.id)
        )

    total_count = (await db.exec(select(func.count(Post.id)).where(*filters))).one()
    posts = (
        await db.exec(
            select(Post)
            .where(*filters)
            .order_by(Post.date_created.desc())
            .offset(offset_delta)
            .limit(limit)
        )
    ).all()

    return PostListResponse(
        total_count=total_count,
        results=[await _to_response(db, p) for p in posts],
    )


#############################################
#              GET POST BY ID               #
#############################################
@posts_router.get(
    "/{post_id}",
    response_model=PostResponse,
    summary="Get a single post by ID",
)
async def get_post(
    post_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> PostResponse:
    post = await db.get(Post, post_id)

    if not post or not _visible(post, current_user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found."
        )

    return await _to_response(db, post)


#############################################
#             LIST POST REPLIES             #
#############################################
@posts_router.get(
    "/{post_id}/replies",
    response_model=PostListResponse,
    summary="List the replies threaded under a post",
)
async def list_post_replies(
    post_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> PostListResponse:
    parent = await db.get(Post, post_id)
    if not parent or not _visible(parent, current_user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found."
        )

    offset_delta = (page - 1) * limit
    filters = [Post.parent_post_id == post_id]
    if not _is_reviewer(current_user):
        filters.append(
            Post.status.not_in(_HIDDEN_STATUSES) | (Post.author_id == current_user.id)
        )

    total_count = (await db.exec(select(func.count(Post.id)).where(*filters))).one()
    replies = (
        await db.exec(
            select(Post)
            .where(*filters)
            .order_by(Post.date_created.asc())
            .offset(offset_delta)
            .limit(limit)
        )
    ).all()

    return PostListResponse(
        total_count=total_count,
        results=[await _to_response(db, r) for r in replies],
    )


#############################################
#                UPDATE POST                #
#############################################
@posts_router.patch(
    "/{post_id}",
    response_model=PostResponse,
    summary="Edit a post's content or status",
)
async def update_post(
    post_id: int,
    payload: PostUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> PostResponse:
    """The author may edit content and move status between their own
    PUBLISHED/DRAFT/ARCHIVED states. Reviewers may additionally set
    DELETED/SUSPENDED (moderation actions) but may not edit content they
    didn't write."""
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found."
        )

    is_owner = post.author_id == current_user.id
    is_reviewer = _is_reviewer(current_user)

    if not is_owner and not is_reviewer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own posts.",
        )

    incoming_data = payload.model_dump(exclude_unset=True)
    if not incoming_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No parameters supplied."
        )

    if "content" in incoming_data and not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the author can edit post content.",
        )

    if (
        "status" in incoming_data
        and incoming_data["status"] in {PostStatus.DELETED, PostStatus.SUSPENDED}
        and not is_reviewer
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a moderator or admin can delete or suspend a post.",
        )

    incoming_data["date_modified"] = datetime.now(timezone.utc)
    incoming_data["modified_by"] = current_user.id

    post.sqlmodel_update(incoming_data)
    db.add(post)
    await db.commit()
    await db.refresh(post)

    return await _to_response(db, post)


#############################################
#                DELETE POST                #
#############################################
@posts_router.delete(
    "/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete a post (author or Admin/Moderator)",
)
async def delete_post(
    post_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """Hard-delete, cascading to media/comments/likes/replies at the DB
    level. For a soft, reversible removal, PATCH status to DELETED instead."""
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found."
        )

    if post.author_id != current_user.id and not _is_reviewer(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own posts.",
        )

    await db.delete(post)
    await db.commit()

    return None
