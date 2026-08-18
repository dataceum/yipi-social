###########################################################################################
# This script defines the Call endpoints: the 3CX webhook receiver, the
# synchronous caller-lookup ("screen pop") endpoint 3CX hits as a call
# rings in, plain call lookup by ID, and the calls-by-user CRM report.
#
# ASSUMPTIONS flagged up front (I don't have your actual config/secrets
# wiring, so these are the pieces you'll need to adapt):
#   - `app.core.config.settings.THREE_CX_WEBHOOK_SECRET` holds a shared
#     secret that 3CX sends back on every request, checked via a header.
#     Swap this for however you actually authenticate server-to-server
#     calls from 3CX (mTLS, IP allowlist, signed payload, etc.) if this
#     header-secret approach isn't what you use.
#   - Phone numbers are normalized to E.164 with a default region of "US"
#     before being matched against User.phone_number (which is already
#     forced into E.164 at write time via PhoneNumberValidator). If your
#     3CX tenant spans multiple countries, this default region needs to
#     come from the extension/trunk configuration instead of being fixed.
###########################################################################################

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Header
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession
import phonenumbers

from app.core.db import get_async_session
from app.core.security import get_current_user
from app.core.config import settings
from app.models.user import User
from app.models.enums import UserRole
from app.models.team import Agent
from app.models.call import (
    Call,
    CallCreate,
    CallResponse,
    CallListResponse,
    CallLookupResponse,
    CallReportResponse,
    CallAgentSummary,
    CallCallerSummary,
)

calls_router = APIRouter(prefix="/calls", tags=["Calls"])


def _is_admin(user: User) -> bool:
    return user.role == UserRole.ADMIN


async def _get_agent_for_user(db: AsyncSession, user_id: int) -> Optional[Agent]:
    return (await db.exec(select(Agent).where(Agent.user_id == user_id))).one_or_none()


def _normalize_phone(raw: str, default_region: str = "GH") -> Optional[str]:
    try:
        parsed = phonenumbers.parse(raw, default_region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(parsed):
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


async def verify_3cx_webhook_secret(
    x_3cx_webhook_secret: str = Header(..., alias="X-3CX-Webhook-Secret"),
) -> None:
    if x_3cx_webhook_secret != settings.THREE_CX_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook credentials.",
        )


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
#   3CX WEBHOOK RECEIVER — upserts by external_call_id, since 3CX  #
#   fires one event per call-state transition (ringing -> answered #
#   -> completed), not one event per call.                          #
####################################################################
@calls_router.post(
    "/webhook",
    response_model=CallResponse,
    dependencies=[Depends(verify_3cx_webhook_secret)],
    summary="Receive a call-event webhook from 3CX",
)
async def receive_call_webhook(
    payload: CallCreate,
    db: AsyncSession = Depends(get_async_session),
) -> CallResponse:
    existing = (
        await db.exec(
            select(Call).where(Call.external_call_id == payload.external_call_id)
        )
    ).one_or_none()

    normalized_number = _normalize_phone(payload.caller_number)
    caller_user_id = None
    if normalized_number:
        matched_user = (
            await db.exec(select(User).where(User.phone_number == normalized_number))
        ).one_or_none()
        if matched_user:
            caller_user_id = matched_user.id

    if existing:
        update_data = payload.model_dump(
            exclude_unset=True, exclude={"external_call_id"}
        )
        # Only overwrite the match if we found one this event; a later
        # event with an unparsable number shouldn't blank out an earlier
        # successful match.
        if caller_user_id is not None:
            update_data["caller_user_id"] = caller_user_id
        update_data["date_modified"] = datetime.now(timezone.utc)

        existing.sqlmodel_update(update_data)
        db.add(existing)
        call = existing
    else:
        call = Call(
            external_call_id=payload.external_call_id,
            caller_number=payload.caller_number,
            direction=payload.direction,
            status=payload.status,
            agent_id=payload.agent_id,
            team_id=payload.team_id,
            caller_user_id=caller_user_id,
            started_at=payload.started_at,
            answered_at=payload.answered_at,
            ended_at=payload.ended_at,
            duration_seconds=payload.duration_seconds,
            recording_url=payload.recording_url,
        )
        db.add(call)

    await db.commit()
    await db.refresh(call)

    return await _to_call_response(call)


####################################################################
#   3CX CALL LOOKUP — synchronous caller-ID ("screen pop") lookup,  #
#   hit while a call is ringing, before/without a Call record       #
#   necessarily existing yet. Distinct from the webhook above.      #
####################################################################
@calls_router.get(
    "/lookup",
    response_model=CallLookupResponse,
    dependencies=[Depends(verify_3cx_webhook_secret)],
    summary="Look up a caller by phone number for 3CX's screen-pop display",
)
async def lookup_caller(
    phone_number: str = Query(..., description="Raw caller ID number from 3CX"),
    db: AsyncSession = Depends(get_async_session),
) -> CallLookupResponse:
    normalized = _normalize_phone(phone_number)
    if not normalized:
        return CallLookupResponse(matched=False, user=None, recent_calls=[])

    user = (
        await db.exec(select(User).where(User.phone_number == normalized))
    ).one_or_none()
    if not user:
        return CallLookupResponse(matched=False, user=None, recent_calls=[])

    recent_calls = (
        await db.exec(
            select(Call)
            .where(Call.caller_user_id == user.id)
            .order_by(Call.started_at.desc())
            .limit(5)
        )
    ).all()

    return CallLookupResponse(
        matched=True,
        user=CallCallerSummary.model_validate(user),
        recent_calls=[await _to_call_response(c) for c in recent_calls],
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
    summary="Get a single call — admins, or an agent on the handling team",
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
