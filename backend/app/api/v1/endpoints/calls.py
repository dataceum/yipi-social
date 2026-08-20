###########################################################################################
# This script defines the internal Call endpoints for CRM staff.
#
# NOTE ON SCOPE:
#   The two 3CX-facing endpoints that previously lived here have been
#   moved/replaced:
#
#   OLD: POST /calls/webhook  (3CX webhook receiver, header-secret auth)
#   OLD: GET  /calls/lookup   (screen-pop, returned CallLookupResponse)
#   → REPLACED BY: GET + POST /api/method/smart_lookup_and_call_log
#     in threecx.py, which matches the XML contract exactly (correct
#     response envelope, DB-backed API key auth, Ghana phone region).
#     CallLookupResponse and CallCreate no longer exist in call.py.
#
#   What remains here are the two internal, staff-authenticated endpoints
#   that were never 3CX-facing:
#     GET /calls/reports/by-user/{user_id}  — calls-by-user CRM report
#     GET /calls/{call_id}                  — fetch a single call record
###########################################################################################

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_async_session
from app.core.security import get_current_user
from app.models.user import User
from app.models.enums import UserRole
from app.models.team import Agent
from app.models.call import (
    Call,
    CallResponse,
    CallListResponse,
    CallReportResponse,
    CallAgentSummary,
    CallCallerSummary,
)

calls_router = APIRouter(prefix="/calls", tags=["Calls"])


def _is_admin(user: User) -> bool:
    return user.role == UserRole.ADMIN


async def _get_agent_for_user(db: AsyncSession, user_id: int) -> Optional[Agent]:
    return (await db.exec(select(Agent).where(Agent.user_id == user_id))).one_or_none()


async def _to_call_response(call: Call) -> CallResponse:
    agent_summary = (
        CallAgentSummary.model_validate(call.agent.user) if call.agent else None
    )
    caller_summary = (
        CallCallerSummary.model_validate(call.caller) if call.caller else None
    )
    return CallResponse(
        id=call.id,
        external_call_id=call.external_call_id,
        caller_number=call.caller_number,
        direction=call.direction,
        status=call.status,
        agent=agent_summary,
        team_id=call.team_id,
        caller=caller_summary,
        started_at=call.started_at,
        answered_at=call.answered_at,
        ended_at=call.ended_at,
        duration_seconds=call.duration_seconds,
        recording_url=call.recording_url,
        date_created=call.date_created,
    )


####################################################################
#              CALLS BY USER — CRM report                          #
####################################################################
@calls_router.get(
    "/reports/by-user/{user_id}",
    response_model=CallReportResponse,
    summary="Report on all calls received from a given user (staff only)",
)
async def calls_by_user_report(
    user_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> CallReportResponse:
    if not (_is_admin(current_user) or await _get_agent_for_user(db, current_user.id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only staff can run call reports.",
        )

    target_user = await db.get(User, user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    filters = [Call.caller_user_id == user_id]
    offset_delta = (page - 1) * limit

    total_count = (await db.exec(select(func.count(Call.id)).where(*filters))).one()
    total_duration = (
        await db.exec(
            select(func.coalesce(func.sum(Call.duration_seconds), 0)).where(*filters)
        )
    ).one()
    calls = (
        await db.exec(
            select(Call)
            .where(*filters)
            .order_by(Call.started_at.desc())
            .offset(offset_delta)
            .limit(limit)
        )
    ).all()

    return CallReportResponse(
        user=CallCallerSummary.model_validate(target_user),
        total_calls=total_count,
        total_duration_seconds=total_duration,
        calls=CallListResponse(
            total_count=total_count,
            results=[await _to_call_response(c) for c in calls],
        ),
    )


####################################################################
#                     GET CALL BY ID                                #
####################################################################
@calls_router.get(
    "/{call_id}",
    response_model=CallResponse,
    summary="Get a single call record — admins, or an agent on the handling team",
)
async def get_call(
    call_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> CallResponse:
    call = await db.get(Call, call_id)
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Call not found."
        )

    if not _is_admin(current_user):
        requester_agent = await _get_agent_for_user(db, current_user.id)
        if not requester_agent or requester_agent.team_id != call.team_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Call not found."
            )

    return await _to_call_response(call)
