###########################################################################################
# This script defines the like endpoints.
###########################################################################################

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.db import get_async_session
from app.core.security import get_current_user
from app.models.user import User
from app.models.post import Post
from app.models.comment import Comment
from app.models.like import (
    Like,
    LikeCreate,
    LikeResponse,
    LikeListResponse,
    LikeAuthorSummary,
)

likes_router = APIRouter(tags=["Likes"])

# Note: Like has no `user` relationship (only `post`/`comment`), so every
# response below fetches the liker explicitly and builds LikeAuthorSummary
# from it rather than relying on relationship traversal.


#############################################
#                LIKE A POST                #
#############################################
@likes_router.post(
    "/posts/{post_id}/likes",
    response_model=LikeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Like a post (self-likes are allowed)",
)
async def like_post(
    post_id: int,
    payload: LikeCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> LikeResponse:
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found."
        )

    like = Like(post_id=post_id, user_id=current_user.id)
    db.add(like)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already liked this post.",
        )

    await db.refresh(like)
    return LikeResponse(
        id=like.id,
        post_id=like.post_id,
        comment_id=None,
        user=LikeAuthorSummary(
            id=current_user.id,
            username=current_user.username,
            first_name=current_user.first_name,
            last_name=current_user.last_name,
        ),
        date_created=like.date_created,
    )


#############################################
#               UNLIKE A POST               #
#############################################
@likes_router.delete(
    "/posts/{post_id}/likes",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove your like from a post",
)
async def unlike_post(
    post_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> None:
    like = (
        await db.exec(
            select(Like).where(Like.post_id == post_id, Like.user_id == current_user.id)
        )
    ).one_or_none()

    if not like:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You haven't liked this post.",
        )

    await db.delete(like)
    await db.commit()
    return None


#############################################
#             LIST A POST'S LIKES           #
#############################################
@likes_router.get(
    "/posts/{post_id}/likes",
    response_model=LikeListResponse,
    summary="List the users who liked a post",
)
async def list_post_likes(
    post_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> LikeListResponse:
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found."
        )

    offset_delta = (page - 1) * limit
    total_count = (
        await db.exec(select(func.count(Like.id)).where(Like.post_id == post_id))
    ).one()
    likes = (
        await db.exec(
            select(Like)
            .where(Like.post_id == post_id)
            .order_by(Like.date_created.desc())
            .offset(offset_delta)
            .limit(limit)
        )
    ).all()

    results = []
    for like in likes:
        liker = await db.get(User, like.user_id)
        results.append(
            LikeResponse(
                id=like.id,
                post_id=like.post_id,
                comment_id=None,
                user=LikeAuthorSummary.model_validate(liker),
                date_created=like.date_created,
            )
        )

    return LikeListResponse(total_count=total_count, results=results)


#############################################
#               LIKE A COMMENT              #
#############################################
@likes_router.post(
    "/comments/{comment_id}/likes",
    response_model=LikeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Like a comment (self-likes are allowed)",
)
async def like_comment(
    comment_id: int,
    payload: LikeCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> LikeResponse:
    comment = await db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found."
        )

    like = Like(comment_id=comment_id, user_id=current_user.id)
    db.add(like)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already liked this comment.",
        )

    await db.refresh(like)
    return LikeResponse(
        id=like.id,
        post_id=None,
        comment_id=like.comment_id,
        user=LikeAuthorSummary(
            id=current_user.id,
            username=current_user.username,
            first_name=current_user.first_name,
            last_name=current_user.last_name,
        ),
        date_created=like.date_created,
    )


#############################################
#              UNLIKE A COMMENT             #
#############################################
@likes_router.delete(
    "/comments/{comment_id}/likes",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove your like from a comment",
)
async def unlike_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> None:
    like = (
        await db.exec(
            select(Like).where(
                Like.comment_id == comment_id, Like.user_id == current_user.id
            )
        )
    ).one_or_none()

    if not like:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You haven't liked this comment.",
        )

    await db.delete(like)
    await db.commit()
    return None


#############################################
#           LIST A COMMENT'S LIKES          #
#############################################
@likes_router.get(
    "/comments/{comment_id}/likes",
    response_model=LikeListResponse,
    summary="List the users who liked a comment",
)
async def list_comment_likes(
    comment_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> LikeListResponse:
    comment = await db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found."
        )

    offset_delta = (page - 1) * limit
    total_count = (
        await db.exec(select(func.count(Like.id)).where(Like.comment_id == comment_id))
    ).one()
    likes = (
        await db.exec(
            select(Like)
            .where(Like.comment_id == comment_id)
            .order_by(Like.date_created.desc())
            .offset(offset_delta)
            .limit(limit)
        )
    ).all()

    results = []
    for like in likes:
        liker = await db.get(User, like.user_id)
        results.append(
            LikeResponse(
                id=like.id,
                post_id=None,
                comment_id=like.comment_id,
                user=LikeAuthorSummary.model_validate(liker),
                date_created=like.date_created,
            )
        )

    return LikeListResponse(total_count=total_count, results=results)
