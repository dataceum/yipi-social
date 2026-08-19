"""
Call model — inbound/outbound call log fed by 3CX webhooks.

A call has two independent participant links, each optional for a
different reason:

  - agent_id: the Agent who answered. Null for calls nobody answered
    (MISSED/FAILED) — the call is still logged against whichever team's
    queue it rang into (team_id), even with no agent attached.

  - caller_user_id: the platform User matched to the caller's phone
    number, resolved server-side at ingestion by matching caller_number
    against User.phone_number. Null whenever the caller isn't a
    registered user — caller_number is always captured either way, so a
    failed match never loses the underlying call data.

This caller_user_id link is what a "calls received from a user" CRM
report is built on: filter Call by caller_user_id, independent of which
agent or team happened to handle it.
"""

from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship, UniqueConstraint
import sqlalchemy as sa
from app.models.enums import CallDirection, CallStatus

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.team import Agent, Team

#########################################################
#                     CALL LAYER                          #
#########################################################


class CallBase(SQLModel):
    caller_number: str = Field(max_length=32)
    direction: CallDirection
    status: CallStatus


class CallCreate(CallBase):
    """
    Populated from the 3CX webhook payload, not submitted directly by end
    users. caller_user_id is intentionally absent here — it's resolved
    server-side (matching caller_number against User.phone_number) rather
    than supplied by the caller.
    """

    external_call_id: str = Field(
        description="3CX's own call identifier — used to de-dupe webhook retries."
    )
    agent_id: Optional[int] = None
    team_id: Optional[int] = None
    started_at: datetime
    answered_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    recording_url: Optional[str] = None


class CallUpdate(SQLModel):
    """For webhook updates as a call progresses (ringing -> answered ->
    completed, etc.) — looked up by external_call_id, not id, at the
    endpoint layer, since 3CX doesn't know our internal ids."""

    status: Optional[CallStatus] = None
    agent_id: Optional[int] = None
    answered_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    recording_url: Optional[str] = None


class Call(CallBase, table=True):
    __tablename__ = "calls"
    __table_args__ = (UniqueConstraint("external_call_id", name="uq_call_external_id"),)

    id: int = Field(default=None, primary_key=True)
    external_call_id: str = Field(index=True)

    # SET NULL rather than CASCADE on all three: deleting an Agent, Team, or
    # User shouldn't erase call history — it should just stop attributing
    # it to a since-removed record.
    agent_id: Optional[int] = Field(
        default=None, foreign_key="agents.id", index=True, ondelete="SET NULL"
    )
    team_id: Optional[int] = Field(
        default=None, foreign_key="teams.id", index=True, ondelete="SET NULL"
    )
    caller_user_id: Optional[int] = Field(
        default=None, foreign_key="users.id", index=True, ondelete="SET NULL"
    )

    started_at: datetime = Field(sa_type=sa.DateTime(timezone=True))
    answered_at: Optional[datetime] = Field(
        default=None, sa_type=sa.DateTime(timezone=True)
    )
    ended_at: Optional[datetime] = Field(
        default=None, sa_type=sa.DateTime(timezone=True)
    )
    duration_seconds: Optional[int] = Field(default=None)
    recording_url: Optional[str] = Field(default=None)

    date_created: datetime = Field(
        sa_type=sa.DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    date_modified: datetime = Field(
        sa_type=sa.DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    agent: Optional["Agent"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[Call.agent_id]",
            "lazy": "selectin",
        },
    )
    team: Optional["Team"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[Call.team_id]",
            "lazy": "selectin",
        },
    )
    caller: Optional["User"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[Call.caller_user_id]",
            "lazy": "selectin",
        },
    )


##########################################################
# OUTGOING RESPONSE PAYLOAD DATA TRANSFER OBJECTS (DTOs) #
##########################################################


class CallAgentSummary(SQLModel):
    id: int
    username: str
    first_name: str
    last_name: str


class CallCallerSummary(SQLModel):
    id: int
    username: str
    first_name: str
    last_name: str


class CallResponse(CallBase):
    id: int
    external_call_id: str
    agent: Optional[CallAgentSummary] = None
    team_id: Optional[int] = None
    caller: Optional[CallCallerSummary] = None
    started_at: datetime
    answered_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    recording_url: Optional[str] = None
    date_created: datetime


class CallListResponse(SQLModel):
    total_count: int
    results: List[CallResponse]


class CallReportResponse(SQLModel):
    """Aggregate report backing 'calls received from a user' — summary
    stats plus the underlying paginated call list."""

    user: CallCallerSummary
    total_calls: int
    total_duration_seconds: int
    calls: CallListResponse


##########################################################
#   3CX CRM CONTRACT SCHEMAS (Scenario 1: Smart Lookup   #
#   GET response + Scenario 2: Journaling POST body)     #
##########################################################


class SmartLookupMessage(SQLModel):
    """
    The inner payload 3CX reads via the variable paths defined in the XML:
      message.contact_id → ContactID / EntityId (passed back to us in the
                           journal POST as contact_id)
      message.first_name → FName
      message.last_name  → LName
      message.url        → RelPath  (concatenated onto CRMBaseURL by 3CX
                           to build the ContactUrl it opens in the browser)

    For KNOWN callers: contact_id is the user's id (str), url is the
    relative path to their profile page (e.g. "/crm/users/42").

    For UNKNOWN callers: contact_id is the E.164 phone number (non-empty,
    so the AllowEmpty="false" rule in the XML still fires the popup),
    first_name/"last_name" are placeholder labels, and url is the relative
    path to the new-user creation form pre-filled with the phone number
    (e.g. "/crm/users/new?phone=%2B233201234567") — satisfying requirement
    3: the agent's browser opens that form the moment the call connects.
    """

    contact_id: str
    first_name: str
    last_name: str
    url: str


class SmartLookupResponse(SQLModel):
    """Wraps SmartLookupMessage in the {"message": {...}} envelope that 3CX
    expects. The XML variable paths are all message.* so this envelope is
    mandatory — a flat response is silently ignored."""

    message: SmartLookupMessage


class ThreeCXJournalPayload(SQLModel):
    """
    Maps the fields 3CX POSTs in Scenario 2 (ReportCall / Hangup).
    Field names match the XML PostValues keys exactly; 'from' is a Python
    reserved word so it's aliased.

    Note on timestamps: 3CX sends CallStartTimeLocal / CallEndTimeLocal —
    local server time, NOT UTC. Parse with your 3CX tenant's timezone
    (see THREE_CX_TIMEZONE in settings) to store correctly as UTC.
    """

    model_config = {"populate_by_name": True}

    id: str  # 3CX CallID → external_call_id
    from_agent: str = Field(alias="from")  # [Agent] — ext or display name
    to: str  # destination number
    agent_ext: str  # extension → look up Agent
    direction: str  # "Inbound" | "Outbound"
    status: str  # "Answered" | "NoAnswer" | "Busy" | "Failed" | "Voicemail"
    duration: str  # total seconds as string (e.g. "72")
    type: str  # 3CX call type label
    number: str  # raw caller number
    contact_id: Optional[str] = None  # EntityId echoed back from lookup
    recording_url: Optional[str] = None
    start_time: str  # "yyyy-MM-dd HH:mm:ss" (local)
    end_time: Optional[str] = None  # "yyyy-MM-dd HH:mm:ss" (local)


class JournalAckResponse(SQLModel):
    """Minimal acknowledgment returned to 3CX after a successful journal
    POST. 3CX doesn't read the body, but a 2xx is required."""

    message: str = "ok"
