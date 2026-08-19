###########################################################################################
# This script implements the two 3CX CRM integration scenarios defined in
# ERPNext_Smart_Lookup.xml, reconciled against our own data model.
#
# HOW IT FITS TOGETHER:
#   The XML configures 3CX with one base URL (CRMBaseURL) and one path
#   (/api/method/smart_lookup_and_call_log) that handles both scenarios:
#
#   Scenario 1 — Smart Lookup (fires when the phone RINGS):
#     GET /api/method/smart_lookup_and_call_log?number=[Number]
#     → Returns {"message": {contact_id, first_name, last_name, url}}
#     → 3CX reads these variables and pops the screen with caller info.
#     → The ContactUrl 3CX opens in the agent's browser is:
#           CRMBaseURL + message.url
#       For known callers  → their profile page  (/crm/users/{id})
#       For unknown callers → new-user form       (/crm/users/new?phone=...)
#       This is what satisfies requirement 3: unknown callers still get
#         a screen pop that opens the creation form.
#
#   Scenario 2 — Call Journaling (fires on HANGUP):
#     POST /api/method/smart_lookup_and_call_log
#     → Upserts a Call row using 3CX's CallID as external_call_id.
#     → Resolves agent by extension, caller by contact_id echoed from
#       the lookup step, maps 3CX status/direction strings to our enums.
#
# SETUP IN 3CX:
#   In the 3CX CRM template, set:
#     CRMBaseURL  → your app's root URL, e.g. https://myapp.com
#     ApiToken    → the "key:secret" token shown when you generated your
#                   API key via POST /api/v1/api-keys
#   No other XML changes are needed.
#
# SETUP IN SETTINGS (only timezone needed — keys live in the DB now):
#   THREE_CX_TIMEZONE — your 3CX tenant's local timezone string
#                       (e.g. "Africa/Accra"). Country="GH" in the XML
#                       confirms Ghana timezone as the default.
###########################################################################################

from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.db import get_async_session
from app.core.security import verify_password
from app.models.api_key import APIKey
from app.models.call import (
    Call,
    JournalAckResponse,
    SmartLookupMessage,
    SmartLookupResponse,
    ThreeCXJournalPayload,
)
from app.models.enums import CallDirection, CallStatus
from app.models.team import Agent
from app.models.user import User

threecx_router = APIRouter(
    prefix="/api/method",
    tags=["3CX Integration"],
)

# The XML sends: Authorization: token KEY:SECRET
# HTTPBearer strips the "token " scheme prefix, leaving "KEY:SECRET".
_bearer = HTTPBearer(auto_error=False)

# 3CX sends "Inbound" / "Outbound" — map to our enum.
_DIRECTION_MAP: dict[str, CallDirection] = {
    "inbound": CallDirection.INBOUND,
    "outbound": CallDirection.OUTBOUND,
}

# 3CX status strings → our enum.
_STATUS_MAP: dict[str, CallStatus] = {
    "answered": CallStatus.ANSWERED,
    "completed": CallStatus.COMPLETED,
    "noanswer": CallStatus.MISSED,
    "no answer": CallStatus.MISSED,
    "busy": CallStatus.FAILED,
    "failed": CallStatus.FAILED,
    "voicemail": CallStatus.VOICEMAIL,
    "ringing": CallStatus.RINGING,
}

# Ghana (GH per Country attribute in the XML): default region for phone
# parsing and timestamp localisation.
_DEFAULT_REGION = "GH"


async def _verify_3cx_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: AsyncSession = Depends(get_async_session),
) -> APIKey:
    """
    Validates the Authorization: token KEY:SECRET header against the
    api_keys table.

    Steps:
      1. Split credentials on the first ":" to get (raw_key, raw_secret).
      2. Look up an active, non-expired APIKey row by raw_key.
      3. Verify raw_secret against the stored bcrypt hash.
      4. Stamp last_used_at so admins can audit which key 3CX is using.

    Returns the validated APIKey so downstream endpoints can read its
    owner_id if needed. A wrong or missing token always returns 401 —
    never 403 — so the caller learns nothing about what exists.
    """
    _unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API credentials.",
    )

    if not credentials:
        raise _unauthorized

    parts = credentials.credentials.split(":", 1)
    if len(parts) != 2:
        raise _unauthorized

    raw_key, raw_secret = parts

    api_key = (
        await db.exec(
            select(APIKey).where(
                APIKey.key == raw_key,
                APIKey.is_active.is_(True),
            )
        )
    ).one_or_none()

    if not api_key:
        raise _unauthorized

    # Check expiry before the bcrypt call — cheap guard first.
    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        raise _unauthorized

    if not verify_password(raw_secret, api_key.hashed_secret):
        raise _unauthorized

    # Stamp last_used_at — non-critical, so we don't rollback the whole
    # request if this commit somehow fails.
    try:
        api_key.last_used_at = datetime.now(timezone.utc)
        db.add(api_key)
        await db.commit()
    except Exception:
        await db.rollback()

    return api_key


def _normalize_phone(raw: str) -> Optional[str]:
    """E.164-normalise a number using the Ghana region as default,
    consistent with User.phone_number storage format."""
    try:
        import phonenumbers

        parsed = phonenumbers.parse(raw, _DEFAULT_REGION)
        if not phonenumbers.is_valid_number(parsed):
            return None
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except Exception:
        return None


def _parse_3cx_timestamp(value: Optional[str]) -> Optional[datetime]:
    """
    3CX sends CallStartTimeLocal / CallEndTimeLocal as
    "yyyy-MM-dd HH:mm:ss" in the tenant's LOCAL timezone.
    We convert to UTC for storage.
    """
    if not value:
        return None
    try:
        tz = ZoneInfo(getattr(settings, "THREE_CX_TIMEZONE", "Africa/Accra"))
        naive = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        return naive.replace(tzinfo=tz).astimezone(ZoneInfo("UTC"))
    except Exception:
        return None


async def _match_user_by_phone(db: AsyncSession, raw_number: str) -> Optional[User]:
    normalized = _normalize_phone(raw_number)
    if not normalized:
        return None
    return (
        await db.exec(select(User).where(User.phone_number == normalized))
    ).one_or_none()


def _build_lookup_message(
    user: Optional[User], normalized_number: Optional[str], raw_number: str
) -> SmartLookupMessage:
    """
    Builds the {"message": {...}} payload 3CX reads.

    KNOWN caller (user found):
      contact_id = str(user.id)    → 3CX stores as EntityId, echoes back
                                      in the journal POST as contact_id.
      url        = /crm/users/{id} → profile page opened when call connects.

    UNKNOWN caller (no match):
      contact_id = E.164 number    → non-empty so AllowEmpty="false" still
                                      fires the screen-pop (requirement 3).
      url        = /crm/users/new?phone=<encoded>
                                   → new-user form, pre-filled with number
                                      so the agent can register on the call.
    """
    if user:
        return SmartLookupMessage(
            contact_id=str(user.id),
            first_name=user.first_name,
            last_name=user.last_name,
            url=f"/crm/users/{user.id}",
        )

    display_number = normalized_number or raw_number
    encoded_number = quote(display_number, safe="")
    return SmartLookupMessage(
        contact_id=display_number,
        first_name="Unknown",
        last_name="Caller",
        url=f"/crm/users/new?phone={encoded_number}",
    )


###############################################################
#   SCENARIO 1: SMART LOOKUP / SCREEN POP (fires on RING)    #
###############################################################
@threecx_router.get(
    "/smart_lookup_and_call_log",
    response_model=SmartLookupResponse,
    summary="3CX Scenario 1: caller screen-pop lookup while phone is ringing",
)
async def smart_lookup(
    number: str = Query(..., description="Raw caller ID number sent by 3CX"),
    db: AsyncSession = Depends(get_async_session),
    _api_key: APIKey = Depends(_verify_3cx_token),
) -> SmartLookupResponse:
    """
    Called by 3CX during the ringing phase (before the agent picks up).
    Matches the caller's number against registered users and returns the
    structured {"message": {...}} body 3CX needs to populate the screen pop
    and open the correct browser URL when the call connects.

    Unknown callers always get a non-empty response (AllowEmpty="false" is
    satisfied by using the E.164 number as contact_id) and their URL points
    to the new-user creation form pre-filled with their number.
    """
    normalized = _normalize_phone(number)
    user = await _match_user_by_phone(db, number)
    return SmartLookupResponse(message=_build_lookup_message(user, normalized, number))


###############################################################
#   SCENARIO 2: CALL JOURNALING (fires on HANGUP)             #
###############################################################
@threecx_router.post(
    "/smart_lookup_and_call_log",
    response_model=JournalAckResponse,
    summary="3CX Scenario 2: log/update a completed call on hangup",
)
async def journal_call(
    payload: ThreeCXJournalPayload,
    db: AsyncSession = Depends(get_async_session),
    _api_key: APIKey = Depends(_verify_3cx_token),
) -> JournalAckResponse:
    """
    Upserts a Call row keyed by 3CX's CallID (external_call_id). If the
    lookup already ran during ringing and we stored a partial row then,
    this updates it with the final status and duration; if no prior row
    exists (e.g. missed calls that skipped the lookup), it creates one.

    Agent is resolved by extension (agent_ext field).
    Caller is resolved by echoed contact_id: an integer string means a
    known user's id from the lookup; any other value is treated as a raw
    phone number and re-matched.
    """
    # ── Resolve direction / status ────────────────────────────────────────
    direction = _DIRECTION_MAP.get(payload.direction.lower(), CallDirection.INBOUND)
    call_status = _STATUS_MAP.get(payload.status.lower(), CallStatus.COMPLETED)

    # ── Resolve duration ──────────────────────────────────────────────────
    try:
        duration_seconds = int(float(payload.duration))
    except (ValueError, TypeError):
        duration_seconds = None

    # ── Resolve timestamps (local → UTC) ──────────────────────────────────
    started_at = _parse_3cx_timestamp(payload.start_time)
    ended_at = _parse_3cx_timestamp(payload.end_time)
    answered_at = started_at if call_status == CallStatus.ANSWERED else None

    # ── Resolve agent by extension ────────────────────────────────────────
    agent_id: Optional[int] = None
    if payload.agent_ext:
        agent = (
            await db.exec(select(Agent).where(Agent.extension == payload.agent_ext))
        ).one_or_none()
        if agent:
            agent_id = agent.id

    # ── Resolve caller_user_id from echoed contact_id ─────────────────────
    # The lookup step sets contact_id to either:
    #   a) str(user.id)  — known user → parse as int
    #   b) E.164 phone   — unknown caller sentinel → re-match by phone
    caller_user_id: Optional[int] = None
    if payload.contact_id:
        try:
            caller_user_id = int(payload.contact_id)
            if not await db.get(User, caller_user_id):
                caller_user_id = None
        except ValueError:
            matched = await _match_user_by_phone(db, payload.contact_id)
            if matched:
                caller_user_id = matched.id

    # ── Upsert by external_call_id ─────────────────────────────────────────
    existing = (
        await db.exec(select(Call).where(Call.external_call_id == payload.id))
    ).one_or_none()

    try:
        if existing:
            existing.status = call_status
            existing.direction = direction
            existing.agent_id = agent_id or existing.agent_id
            existing.caller_user_id = caller_user_id or existing.caller_user_id
            existing.answered_at = answered_at or existing.answered_at
            existing.ended_at = ended_at or existing.ended_at
            existing.duration_seconds = duration_seconds
            existing.recording_url = payload.recording_url or existing.recording_url
            db.add(existing)
        else:
            normalized = _normalize_phone(payload.number)
            team_id: Optional[int] = None
            if agent_id:
                a = await db.get(Agent, agent_id)
                team_id = a.team_id if a else None

            call = Call(
                external_call_id=payload.id,
                caller_number=normalized or payload.number,
                direction=direction,
                status=call_status,
                agent_id=agent_id,
                team_id=team_id,
                caller_user_id=caller_user_id,
                started_at=started_at,
                answered_at=answered_at,
                ended_at=ended_at,
                duration_seconds=duration_seconds,
                recording_url=payload.recording_url,
            )
            db.add(call)

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return JournalAckResponse()
