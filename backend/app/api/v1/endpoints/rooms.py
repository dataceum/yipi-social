###########################################################################################
# This script defines the room endpoints (live audio/video rooms and chat threads).
###########################################################################################

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.db import get_async_session
from app.core.security import get_current_user
from app.models.user import User
from app.models.enums import UserRole, RoomType, RoomRole, RoomStatus
from app.models.room import (
    Room,
    RoomMember,
    RoomMessage,
    RoomCreate,
    RoomUpdate,
    RoomMessageCreate,
    RoomResponse,
    RoomListResponse,
    RoomMemberResponse,
    RoomMemberListResponse,
    RoomMemberSummary,
    RoomMessageResponse,
    RoomMessageListResponse,
)

rooms_router = APIRouter(prefix="/rooms", tags=["Rooms"])


def _is_reviewer(user: User) -> bool:
    return user.role in {UserRole.ADMIN, UserRole.MODERATOR}


def _to_room_response(room: Room) -> RoomResponse:
    return RoomResponse(
        id=room.id,
        owner_id=room.owner_id,
        room_type=room.room_type,
        name=room.name,
        description=room.description,
        room_picture_url=room.room_picture_url,
        status=room.status,
        stream_url=room.stream_url,
        scheduled_start=room.scheduled_start,
        started_at=room.started_at,
        ended_at=room.ended_at,
        is_suspended=room.is_suspended,
        member_count=len(room.members),
        date_created=room.date_created,
        date_modified=room.date_modified,
        modified_by=room.modified_by,
    )


async def _is_member(db: AsyncSession, room_id: int, user_id: int) -> bool:
    member = (
        await db.exec(
            select(RoomMember).where(
                RoomMember.room_id == room_id, RoomMember.user_id == user_id
            )
        )
    ).one_or_none()
    return member is not None


async def _can_view(db: AsyncSession, room: Room, current_user: User) -> bool:
    if _is_reviewer(current_user) or room.owner_id == current_user.id:
        return True
    if room.is_suspended:
        return False
    if room.room_type == RoomType.CHAT:
        return await _is_member(db, room.id, current_user.id)
    return True  # non-suspended LIVE_AUDIO/LIVE_VIDEO rooms are publicly visible


#############################################
#                CREATE ROOM                #
#############################################
@rooms_router.post(
    "",
    response_model=RoomResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a live audio/video room or a chat thread",
)
async def create_room(
    payload: RoomCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> RoomResponse:
    """The creator is enrolled as OWNER automatically. participant_ids seeds
    additional MEMBER participants (e.g. the other party in a 1:1 chat)."""
    room = Room(
        room_type=payload.room_type,
        name=payload.name,
        description=payload.description,
        room_picture_url=payload.room_picture_url,
        owner_id=current_user.id,
    )
    db.add(room)

    try:
        await db.flush()  # assign room.id

        db.add(
            RoomMember(room_id=room.id, user_id=current_user.id, role=RoomRole.OWNER)
        )

        seen = {current_user.id}
        for participant_id in payload.participant_ids:
            if participant_id in seen:
                continue
            seen.add(participant_id)

            participant = await db.get(User, participant_id)
            if not participant:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"User {participant_id} not found.",
                )
            db.add(
                RoomMember(
                    room_id=room.id, user_id=participant_id, role=RoomRole.MEMBER
                )
            )

        await db.commit()
        await db.refresh(room)
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise

    return _to_room_response(room)


#############################################
#                 LIST ROOMS                #
#############################################
@rooms_router.get(
    "",
    response_model=RoomListResponse,
    summary="List rooms visible to the current user",
)
async def list_rooms(
    room_type: RoomType | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> RoomListResponse:
    """Reviewers see every room. Standard users see: non-suspended LIVE
    rooms (public), plus any room (of either type) they own or belong to."""
    offset_delta = (page - 1) * limit
    filters = []
    if room_type is not None:
        filters.append(Room.room_type == room_type)

    if not _is_reviewer(current_user):
        member_room_ids_subq = select(RoomMember.room_id).where(
            RoomMember.user_id == current_user.id
        )
        filters.append(
            ((Room.room_type != RoomType.CHAT) & (Room.is_suspended.is_(False)))
            | Room.id.in_(member_room_ids_subq)
            | (Room.owner_id == current_user.id)
        )

    total_count = (await db.exec(select(func.count(Room.id)).where(*filters))).one()
    rooms = (
        await db.exec(
            select(Room)
            .where(*filters)
            .order_by(Room.date_created.desc())
            .offset(offset_delta)
            .limit(limit)
        )
    ).all()

    return RoomListResponse(
        total_count=total_count, results=[_to_room_response(r) for r in rooms]
    )


#############################################
#              GET ROOM BY ID               #
#############################################
@rooms_router.get(
    "/{room_id}",
    response_model=RoomResponse,
    summary="Get a single room by ID",
)
async def get_room(
    room_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> RoomResponse:
    room = await db.get(Room, room_id)
    if not room or not await _can_view(db, room, current_user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found."
        )

    return _to_room_response(room)


#############################################
#                UPDATE ROOM                #
#############################################
@rooms_router.patch(
    "/{room_id}",
    response_model=RoomResponse,
    summary="Update room details or live-session status (owner only)",
)
async def update_room(
    room_id: int,
    payload: RoomUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> RoomResponse:
    """Suspension is not settable here — it's managed automatically by the
    report-moderation workflow (see reports.py)."""
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found."
        )

    if room.owner_id != current_user.id and not _is_reviewer(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only modify a room you own.",
        )

    if room.is_suspended:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This room is suspended pending moderation review.",
        )

    incoming_data = payload.model_dump(exclude_unset=True)
    if not incoming_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No parameters supplied."
        )

    if "status" in incoming_data and incoming_data["status"] is not None:
        now = datetime.now(timezone.utc)
        if incoming_data["status"] == RoomStatus.LIVE and room.started_at is None:
            incoming_data["started_at"] = now
        if incoming_data["status"] == RoomStatus.ENDED:
            incoming_data["ended_at"] = now

    incoming_data["date_modified"] = datetime.now(timezone.utc)
    incoming_data["modified_by"] = current_user.id

    room.sqlmodel_update(incoming_data)
    db.add(room)
    await db.commit()
    await db.refresh(room)

    return _to_room_response(room)


#############################################
#                DELETE ROOM                #
#############################################
@rooms_router.delete(
    "/{room_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete a room (owner or Admin/Moderator)",
)
async def delete_room(
    room_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """Cascades to members, messages, and reports at the DB level."""
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found."
        )

    if room.owner_id != current_user.id and not _is_reviewer(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete a room you own.",
        )

    await db.delete(room)
    await db.commit()

    return None


#############################################
#           JOIN ROOM / ADD MEMBER          #
#############################################
@rooms_router.post(
    "/{room_id}/members",
    response_model=RoomMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Join a room yourself, or (owner/reviewer) add another user",
)
async def add_room_member(
    room_id: int,
    user_id: int | None = Query(
        None, description="Add this user instead of self; owner/reviewer only"
    ),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> RoomMemberResponse:
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found."
        )
    if room.is_suspended:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This room is suspended."
        )

    target_id = user_id if user_id is not None else current_user.id

    if target_id != current_user.id:
        if room.owner_id != current_user.id and not _is_reviewer(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the room owner can add other participants.",
            )
    elif room.room_type == RoomType.CHAT and room.owner_id != current_user.id:
        # Private chat threads are invite-only — no self-serve join.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This chat thread is invite-only.",
        )

    target_user = await db.get(User, target_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    member = RoomMember(room_id=room_id, user_id=target_id, role=RoomRole.MEMBER)
    db.add(member)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this room.",
        )

    await db.refresh(member)
    return RoomMemberResponse(
        id=member.id,
        room_id=member.room_id,
        user=RoomMemberSummary.model_validate(target_user),
        role=member.role,
        is_speaker=member.is_speaker,
        is_muted=member.is_muted,
        date_joined=member.date_joined,
        date_left=member.date_left,
    )


#############################################
#          LEAVE ROOM / REMOVE MEMBER       #
#############################################
@rooms_router.delete(
    "/{room_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Leave a room yourself, or (owner/reviewer) remove another user",
)
async def remove_room_member(
    room_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> None:
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found."
        )

    if user_id != current_user.id:
        if room.owner_id != current_user.id and not _is_reviewer(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the room owner can remove other participants.",
            )

    member = (
        await db.exec(
            select(RoomMember).where(
                RoomMember.room_id == room_id, RoomMember.user_id == user_id
            )
        )
    ).one_or_none()

    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That user is not a member of this room.",
        )

    await db.delete(member)
    await db.commit()

    return None


#############################################
#               LIST ROOM MEMBERS           #
#############################################
@rooms_router.get(
    "/{room_id}/members",
    response_model=RoomMemberListResponse,
    summary="List a room's participants",
)
async def list_room_members(
    room_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> RoomMemberListResponse:
    room = await db.get(Room, room_id)
    if not room or not await _can_view(db, room, current_user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found."
        )

    offset_delta = (page - 1) * limit
    total_count = (
        await db.exec(
            select(func.count(RoomMember.id)).where(RoomMember.room_id == room_id)
        )
    ).one()
    members = (
        await db.exec(
            select(RoomMember)
            .where(RoomMember.room_id == room_id)
            .order_by(RoomMember.date_joined.asc())
            .offset(offset_delta)
            .limit(limit)
        )
    ).all()

    results = []
    for m in members:
        user = await db.get(User, m.user_id)
        results.append(
            RoomMemberResponse(
                id=m.id,
                room_id=m.room_id,
                user=RoomMemberSummary.model_validate(user),
                role=m.role,
                is_speaker=m.is_speaker,
                is_muted=m.is_muted,
                date_joined=m.date_joined,
                date_left=m.date_left,
            )
        )

    return RoomMemberListResponse(total_count=total_count, results=results)


#############################################
#               SEND ROOM MESSAGE           #
#############################################
@rooms_router.post(
    "/{room_id}/messages",
    response_model=RoomMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send a message into a room's conversation",
)
async def create_room_message(
    room_id: int,
    payload: RoomMessageCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> RoomMessageResponse:
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found."
        )
    if room.is_suspended:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This room is suspended."
        )
    if not await _is_member(db, room_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only room participants can post messages.",
        )

    message = RoomMessage(
        content=payload.content, room_id=room_id, author_id=current_user.id
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)

    return RoomMessageResponse(
        id=message.id,
        content=message.content,
        room_id=message.room_id,
        author=RoomMemberSummary.model_validate(current_user),
        date_created=message.date_created,
        date_modified=message.date_modified,
    )


#############################################
#              LIST ROOM MESSAGES           #
#############################################
@rooms_router.get(
    "/{room_id}/messages",
    response_model=RoomMessageListResponse,
    summary="List a room's message history",
)
async def list_room_messages(
    room_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> RoomMessageListResponse:
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found."
        )
    if not _is_reviewer(current_user) and not await _is_member(
        db, room_id, current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only room participants can view messages.",
        )

    offset_delta = (page - 1) * limit
    total_count = (
        await db.exec(
            select(func.count(RoomMessage.id)).where(RoomMessage.room_id == room_id)
        )
    ).one()
    messages = (
        await db.exec(
            select(RoomMessage)
            .where(RoomMessage.room_id == room_id)
            .order_by(RoomMessage.date_created.asc())
            .offset(offset_delta)
            .limit(limit)
        )
    ).all()

    results = []
    for m in messages:
        author = await db.get(User, m.author_id)
        results.append(
            RoomMessageResponse(
                id=m.id,
                content=m.content,
                room_id=m.room_id,
                author=RoomMemberSummary.model_validate(author),
                date_created=m.date_created,
                date_modified=m.date_modified,
            )
        )

    return RoomMessageListResponse(total_count=total_count, results=results)
