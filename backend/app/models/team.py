"""
CRM module — Team and Agent models.

This is a deliberately separate bounded context from the social-platform
models (post.py, comment.py, room.py, etc.). An Agent is the CRM identity
for a staff member (MODERATOR/ADMIN role) who handles inbound calls,
analogous to how Profile is the social identity for a standard User —
neither User nor Profile is modified by this module, and nothing here
feeds into the public User-visibility endpoints in users.py. "Can this
team see that user" is a question answered entirely within this module's
own endpoints.

Ownership mechanic: Team intentionally has no owner_id FK back to Agent —
that would make Team depend on Agent and Agent depend on Team, a circular
FK that has to be created in two steps. Instead, Agent carries a `role`
(OWNER/MEMBER); "owner" is just which agent in a team holds that role,
kept to exactly one via a partial unique index. That's what lets team
creation be implicit: an endpoint creating the first Agent for a
not-yet-existing team name creates the Team as a side effect and gives
that agent role=OWNER; creating an Agent against an existing team is only
permitted (at the endpoint layer) for that team's current OWNER, and the
new agent gets role=MEMBER.
"""

from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship, UniqueConstraint
import sqlalchemy as sa
from app.models.enums import AgentRole

if TYPE_CHECKING:
    from app.models.user import User

#########################################################
#                     TEAM LAYER                         #
#########################################################


class TeamBase(SQLModel):
    name: str = Field(min_length=3, max_length=100, unique=True, index=True)
    description: Optional[str] = Field(default=None, max_length=500)


class TeamUpdate(SQLModel):
    """Owner-only, enforced at the endpoint layer — there is no direct
    "create a team" schema; a team only ever comes into existence as a
    side effect of AgentCreate (see below)."""

    name: Optional[str] = None
    description: Optional[str] = None


class Team(TeamBase, table=True):
    __tablename__ = "teams"

    id: int = Field(default=None, primary_key=True)

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

    agents: List["Agent"] = Relationship(
        back_populates="team",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "lazy": "selectin",
        },
    )


#########################################################
#                    AGENT LAYER                          #
#########################################################


class AgentBase(SQLModel):
    # 3CX extension this agent answers on. Optional since it may be
    # provisioned in 3CX moments after the Agent record is created here.
    extension: Optional[str] = Field(default=None, max_length=20)


class AgentCreate(AgentBase):
    """
    user_id is the User (must already hold MODERATOR or ADMIN role — checked
    at the endpoint layer, not the DB, since that's a cross-table business
    rule) being provisioned as an agent.

    team_name selects the team by name:
      - if no team with that name exists yet, it is created here and this
        agent becomes its OWNER;
      - if it already exists, this call only succeeds (endpoint-enforced)
        when the requester is that team's current OWNER, and the new agent
        is added as a MEMBER.
    """

    user_id: int
    team_name: str = Field(min_length=3, max_length=100)


class AgentUpdate(SQLModel):
    """Reassigning role/team is an owner/admin action handled by dedicated
    endpoints (promote, transfer, remove) rather than a general PATCH —
    this update is limited to an agent's own non-structural fields."""

    extension: Optional[str] = None


class Agent(AgentBase, table=True):
    __tablename__ = "agents"
    __table_args__ = (
        # One Agent record per User — mirrors Profile's 1:1 relationship
        # with User.
        UniqueConstraint("user_id", name="uq_agent_user"),
        # Exactly one OWNER per team.
        sa.Index(
            "uq_agent_team_owner",
            "team_id",
            unique=True,
            postgresql_where=sa.text("role = 'owner'"),
        ),
    )

    id: int = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    team_id: int = Field(foreign_key="teams.id", index=True, ondelete="CASCADE")
    role: AgentRole = Field(
        sa_column=sa.Column(
            sa.Enum(AgentRole, name="agent_role_enum", create_type=False),
            nullable=False,
        ),
        default=AgentRole.MEMBER,
    )

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

    team: "Team" = Relationship(
        back_populates="agents",
        sa_relationship_kwargs={
            "foreign_keys": "[Agent.team_id]",
            "lazy": "selectin",
        },
    )
    user: "User" = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[Agent.user_id]",
            "lazy": "selectin",
        },
    )


##########################################################
# OUTGOING RESPONSE PAYLOAD DATA TRANSFER OBJECTS (DTOs) #
##########################################################


class AgentUserSummary(SQLModel):
    id: int
    username: str
    first_name: str
    last_name: str


class AgentResponse(AgentBase):
    id: int
    team_id: int
    user: AgentUserSummary
    role: AgentRole
    date_created: datetime
    date_modified: datetime


class AgentListResponse(SQLModel):
    total_count: int
    results: List[AgentResponse]


class TeamResponse(TeamBase):
    id: int
    agent_count: int = 0
    date_created: datetime
    date_modified: datetime
    modified_by: Optional[int] = None


class TeamListResponse(SQLModel):
    total_count: int
    results: List[TeamResponse]
