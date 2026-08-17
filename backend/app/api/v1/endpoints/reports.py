###########################################################################################
# This script defines the report endpoints.
#
# Filing a report against a Post or Room immediately suspends that Post/Room
# AND its creator (mirroring the existing Profile-suspension mechanism: the
# creator's Profile.status is set to SUSPENDED and User.is_active is set to
# False, exactly like the "status" branch in update_user() in users.py).
# This is a precautionary, review-pending action, not a final verdict.
#
# The report itself is then moderated the same way a Profile is: an Admin or
# Moderator reviews it and transitions its status via PATCH — DISMISSED
# reverses the suspension (unless another open report justifies keeping it
# suspended); RESOLVED confirms the violation and leaves the suspension in
# place.
###########################################################################################

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.db import get_async_session
from app.core.security import get_current_user
from app.models.user import User
from app.models.enums import UserRole, PostStatus, ProfileStatus, ReportStatus
from app.models.post import Post
from app.models.room import Room
from app.models.report import (
    Report,
    ReportCreate,
    ReportUpdate,
    ReportResponse,
    ReportListResponse,
    ReportReporterSummary,
)

reports_router = APIRouter(prefix="/reports", tags=["Reports"])


def _is_reviewer(user: User) -> bool:
    return user.role in {UserRole.ADMIN, UserRole.MODERATOR}


def _to_response(report: Report) -> ReportResponse:
    return ReportResponse(
        id=report.id,
        reason=report.reason,
        details=report.details,
        post_id=report.post_id,
        room_id=report.room_id,
        reporter=ReportReporterSummary.model_validate(report.reporter),
        status=report.status,
        resolution_notes=report.resolution_notes,
        reviewed_by=report.reviewed_by,
        date_created=report.date_created,
        date_modified=report.date_modified,
    )


async def _suspend_creator(db: AsyncSession, creator: User) -> None:
    """Same mechanism update_user() uses when a Profile's status leaves
    APPROVED: is_active goes False, and the Profile itself is marked
    SUSPENDED so this reads consistently everywhere else in the app."""
    creator.is_active = False
    db.add(creator)

    if creator.profile:
        creator.profile.status = ProfileStatus.SUSPENDED
        creator.profile.date_modified = datetime.now(timezone.utc)
        db.add(creator.profile)


async def _reactivate_creator_if_clear(db: AsyncSession, creator: User) -> None:
    """Only lift a creator's suspension if they have no other PENDING or
    UNDER_REVIEW report outstanding — a different valid report shouldn't
    get silently undone by this one being dismissed."""
    other_open_reports = (
        await db.exec(
            select(func.count(Report.id)).where(
                Report.status.in_([ReportStatus.PENDING, ReportStatus.UNDER_REVIEW]),
                (
                    Report.post_id.in_(
                        select(Post.id).where(Post.author_id == creator.id)
                    )
                )
                | (
                    Report.room_id.in_(
                        select(Room.id).where(Room.owner_id == creator.id)
                    )
                ),
            )
        )
    ).one()

    if other_open_reports > 0:
        return

    creator.is_active = True
    db.add(creator)

    if creator.profile and creator.profile.status == ProfileStatus.SUSPENDED:
        creator.profile.status = ProfileStatus.APPROVED
        creator.profile.date_modified = datetime.now(timezone.utc)
        db.add(creator.profile)


#############################################
#               REPORT A POST               #
#############################################
@reports_router.post(
    "/posts/{post_id}",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Report a post for violating community standards",
)
async def report_post(
    post_id: int,
    payload: ReportCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> ReportResponse:
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found."
        )

    if post.author_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You can't report your own post.",
        )

    report = Report(
        reason=payload.reason,
        details=payload.details,
        post_id=post_id,
        reporter_id=current_user.id,
    )
    db.add(report)

    try:
        post.status = PostStatus.SUSPENDED
        post.date_modified = datetime.now(timezone.utc)
        db.add(post)

        creator = await db.get(User, post.author_id)
        await _suspend_creator(db, creator)

        await db.commit()
        await db.refresh(report)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already reported this post.",
        )
    except Exception:
        await db.rollback()
        raise

    return _to_response(report)


#############################################
#               REPORT A ROOM               #
#############################################
@reports_router.post(
    "/rooms/{room_id}",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Report a room for violating community standards",
)
async def report_room(
    room_id: int,
    payload: ReportCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> ReportResponse:
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found."
        )

    if room.owner_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You can't report your own room.",
        )

    report = Report(
        reason=payload.reason,
        details=payload.details,
        room_id=room_id,
        reporter_id=current_user.id,
    )
    db.add(report)

    try:
        room.is_suspended = True
        room.date_modified = datetime.now(timezone.utc)
        db.add(room)

        creator = await db.get(User, room.owner_id)
        await _suspend_creator(db, creator)

        await db.commit()
        await db.refresh(report)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already reported this room.",
        )
    except Exception:
        await db.rollback()
        raise

    return _to_response(report)


#############################################
#                LIST REPORTS                #
#############################################
@reports_router.get(
    "",
    response_model=ReportListResponse,
    summary="List reports for moderation (Admin/Moderator only)",
)
async def list_reports(
    report_status: ReportStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> ReportListResponse:
    if not _is_reviewer(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and moderators can view reports.",
        )

    offset_delta = (page - 1) * limit
    filters = []
    if report_status is not None:
        filters.append(Report.status == report_status)

    total_count = (await db.exec(select(func.count(Report.id)).where(*filters))).one()
    reports = (
        await db.exec(
            select(Report)
            .where(*filters)
            .order_by(Report.date_created.asc())
            .offset(offset_delta)
            .limit(limit)
        )
    ).all()

    return ReportListResponse(
        total_count=total_count, results=[_to_response(r) for r in reports]
    )


#############################################
#              GET REPORT BY ID             #
#############################################
@reports_router.get(
    "/{report_id}",
    response_model=ReportResponse,
    summary="Get a single report (Admin/Moderator only)",
)
async def get_report(
    report_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> ReportResponse:
    if not _is_reviewer(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and moderators can view reports.",
        )

    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found."
        )

    return _to_response(report)


###########################################################
#   MODERATE A REPORT — same workflow shape as Profile    #
#   moderation in users.py's update_user().                #
###########################################################
@reports_router.patch(
    "/{report_id}",
    response_model=ReportResponse,
    summary="Moderate a report: move it through the review workflow",
)
async def update_report(
    report_id: int,
    payload: ReportUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> ReportResponse:
    """DISMISSED reverses the target's and creator's suspension (unless the
    creator has another open report). RESOLVED confirms the violation and
    leaves the existing suspension in place. UNDER_REVIEW is a neutral
    in-progress marker."""
    if not _is_reviewer(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and moderators can moderate reports.",
        )

    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found."
        )

    incoming_data = payload.model_dump(exclude_unset=True)
    if not incoming_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No parameters supplied."
        )

    new_status = incoming_data.get("status")

    try:
        if new_status == ReportStatus.DISMISSED:
            if report.post_id is not None:
                post = await db.get(Post, report.post_id)
                if post and post.status == PostStatus.SUSPENDED:
                    post.status = PostStatus.PUBLISHED
                    post.date_modified = datetime.now(timezone.utc)
                    db.add(post)
                creator = await db.get(User, post.author_id) if post else None
            else:
                room = await db.get(Room, report.room_id)
                if room and room.is_suspended:
                    room.is_suspended = False
                    room.date_modified = datetime.now(timezone.utc)
                    db.add(room)
                creator = await db.get(User, room.owner_id) if room else None

            if creator:
                await _reactivate_creator_if_clear(db, creator)

        incoming_data["reviewed_by"] = current_user.id
        incoming_data["date_modified"] = datetime.now(timezone.utc)

        report.sqlmodel_update(incoming_data)
        db.add(report)

        await db.commit()
        await db.refresh(report)
    except Exception:
        await db.rollback()
        raise

    return _to_response(report)
