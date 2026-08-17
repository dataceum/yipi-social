###########################################################################################
# This script defines the comment endpoints.
###########################################################################################

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_async_session
from app.core.security import get_current_user
from app.models.user import User
from app.models.enums import UserRole
from app.models.post import Post
from app.models.comment import (
    Comment,
    CommentCreate,
    CommentUpdate,
    CommentResponse,
    CommentListResponse,
    CommentAuthorSummary,
)

comments_router = APIRouter(tags=["Comments"])


def _is_reviewer(user: User) -> bool:
    return user.role in {UserRole.ADMIN, UserRole.MODERATOR}


async def _to_response(db: AsyncSession, comment: Comment) -> CommentResponse:
    reply_count = (
        await db.exec(
            select(func.count(Comment.id)).where(
                Comment.parent_comment_id == comment.id
            )
        )
    ).one()
    return CommentResponse(
        id=comment.id,
        content=comment.content,
        post_id=comment.post_id,
        parent_comment_id=comment.parent_comment_id,
        author=CommentAuthorSummary.model_validate(comment.author),
        reply_count=reply_count,
        like_count=len(comment.likes),
        date_created=comment.date_created,
        date_modified=comment.date_modified,
    )


#############################################
#           CREATE COMMENT ON POST          #
#############################################
@comments_router.post(
    "/posts/{post_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Comment on a post, optionally replying to another comment",
)
async def create_comment(
    post_id: int,
    payload: CommentCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> CommentResponse:
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found."
        )

    if payload.parent_comment_id is not None:
        parent = await db.get(Comment, payload.parent_comment_id)
        if not parent or parent.post_id != post_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent comment not found on this post.",
            )

    comment = Comment(
        content=payload.content,
        post_id=post_id,
        author_id=current_user.id,
        parent_comment_id=payload.parent_comment_id,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    return await _to_response(db, comment)


#############################################
#         LIST TOP-LEVEL POST COMMENTS      #
#############################################
@comments_router.get(
    "/posts/{post_id}/comments",
    response_model=CommentListResponse,
    summary="List a post's top-level comments",
)
async def list_post_comments(
    post_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> CommentListResponse:
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found."
        )

    offset_delta = (page - 1) * limit
    filters = [Comment.post_id == post_id, Comment.parent_comment_id.is_(None)]

    total_count = (await db.exec(select(func.count(Comment.id)).where(*filters))).one()
    comments = (
        await db.exec(
            select(Comment)
            .where(*filters)
            .order_by(Comment.date_created.asc())
            .offset(offset_delta)
            .limit(limit)
        )
    ).all()

    return CommentListResponse(
        total_count=total_count,
        results=[await _to_response(db, c) for c in comments],
    )


#############################################
#             LIST COMMENT REPLIES          #
#############################################
@comments_router.get(
    "/comments/{comment_id}/replies",
    response_model=CommentListResponse,
    summary="List the replies threaded under a comment",
)
async def list_comment_replies(
    comment_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> CommentListResponse:
    parent = await db.get(Comment, comment_id)
    if not parent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found."
        )

    offset_delta = (page - 1) * limit
    filters = [Comment.parent_comment_id == comment_id]

    total_count = (await db.exec(select(func.count(Comment.id)).where(*filters))).one()
    replies = (
        await db.exec(
            select(Comment)
            .where(*filters)
            .order_by(Comment.date_created.asc())
            .offset(offset_delta)
            .limit(limit)
        )
    ).all()

    return CommentListResponse(
        total_count=total_count,
        results=[await _to_response(db, r) for r in replies],
    )


#############################################
#               UPDATE COMMENT              #
#############################################
@comments_router.patch(
    "/comments/{comment_id}",
    response_model=CommentResponse,
    summary="Edit a comment's content (author only)",
)
async def update_comment(
    comment_id: int,
    payload: CommentUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> CommentResponse:
    comment = await db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found."
        )

    if comment.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own comments.",
        )

    comment.content = payload.content
    comment.date_modified = datetime.now(timezone.utc)
    comment.modified_by = current_user.id

    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    return await _to_response(db, comment)


#############################################
#               DELETE COMMENT              #
#############################################
@comments_router.delete(
    "/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a comment (author or Admin/Moderator)",
)
async def delete_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """Cascades to replies and likes at the DB level."""
    comment = await db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found."
        )

    if comment.author_id != current_user.id and not _is_reviewer(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own comments.",
        )

    await db.delete(comment)
    await db.commit()

    return None
