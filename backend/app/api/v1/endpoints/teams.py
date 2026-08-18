###########################################################################################
# This script defines the Team and Agent endpoints (CRM module).
#
# Two ASSUMPTIONS worth flagging up front, since I don't have your actual
# auth/config wiring:
#   - "Founding" a new team (team_name doesn't exist yet) requires either
#     an ADMIN, or the target user provisioning themselves
#     (payload.user_id == current_user.id). A MODERATOR cannot found a
#     team on someone else's behalf — only for themselves, or an admin
#     does it for them.
#   - Everything else follows the stated rule literally: only the team's
#     OWNER agent (or an ADMIN) can add further agents to an existing team.
###########################################################################################

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.db import get_async_session
from app.core.security import get_current_user
from app.models.user import User
from app.models.enums import UserRole, AgentRole
from app.models.team import (
    Team,
    Agent,
    TeamUpdate,
    TeamResponse,
    TeamListResponse,
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    AgentListResponse,
    AgentUserSummary,
)

teams_router = APIRouter(tags=["Teams", "Agents"])


def _is_admin(user: User) -> bool:
    return user.role == UserRole.ADMIN


async def _get_agent_for_user(db: AsyncSession, user_id: int) -> Agent | None:
    return (await db.exec(select(Agent).where(Agent.user_id == user_id))).one_or_none()


def _to_team_response(team: Team) -> TeamResponse:
    return TeamResponse(
        id=team.id,
        name=team.name,
        description=team.description,
        agent_count=len(team.agents),
        date_created=team.date_created,
        date_modified=team.date_modified,
        modified_by=team.modified_by,
    )


def _to_agent_response(agent: Agent) -> AgentResponse:
    return AgentResponse(
        id=agent.id,
        team_id=agent.team_id,
        user=AgentUserSummary.model_validate(agent.user),
        role=agent.role,
        extension=agent.extension,
        date_created=agent.date_created,
        date_modified=agent.date_modified,
    )


#####################################################
#     PROVISION AN AGENT (implicitly creates the    #
#     team the first time it's referenced)          #
#####################################################
@teams_router.post(
    "/agents",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Provision a moderator/admin as an agent, founding their team if new",
)
async def create_agent(
    payload: AgentCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> AgentResponse:
    target_user = await db.get(User, payload.user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    if target_user.role not in {UserRole.MODERATOR, UserRole.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only moderator or admin accounts can be provisioned as agents.",
        )

    if await _get_agent_for_user(db, payload.user_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This user is already an agent.",
        )

    team = (
        await db.exec(select(Team).where(Team.name == payload.team_name))
    ).one_or_none()

    try:
        if team is None:
            if not (_is_admin(current_user) or payload.user_id == current_user.id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "Only an admin can found a new team on someone else's "
                        "behalf — moderators may only found a team for themselves."
                    ),
                )
            team = Team(name=payload.team_name)
            db.add(team)
            await db.flush()  # assign team.id
            role = AgentRole.OWNER
        else:
            requester_agent = await _get_agent_for_user(db, current_user.id)
            is_owner = (
                requester_agent is not None
                and requester_agent.team_id == team.id
                and requester_agent.role == AgentRole.OWNER
            )
            if not (_is_admin(current_user) or is_owner):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the team's owner or an admin can add agents to this team.",
                )
            role = AgentRole.MEMBER

        agent = Agent(
            user_id=payload.user_id,
            team_id=team.id,
            role=role,
            extension=payload.extension,
        )
        db.add(agent)
        await db.commit()
        await db.refresh(agent)
    except HTTPException:
        await db.rollback()
        raise
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That team name or user is already in use as an agent.",
        )
    except Exception:
        await db.rollback()
        raise

    return _to_agent_response(agent)


#############################################
#                LIST TEAMS                 #
#############################################
@teams_router.get(
    "/teams",
    response_model=TeamListResponse,
    summary="List teams — admins see all; agents see only their own",
)
async def list_teams(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> TeamListResponse:
    filters = []

    if not _is_admin(current_user):
        requester_agent = await _get_agent_for_user(db, current_user.id)
        if not requester_agent:
            return TeamListResponse(total_count=0, results=[])
        filters.append(Team.id == requester_agent.team_id)

    offset_delta = (page - 1) * limit
    total_count = (await db.exec(select(func.count(Team.id)).where(*filters))).one()
    teams = (
        await db.exec(
            select(Team)
            .where(*filters)
            .order_by(Team.date_created.desc())
            .offset(offset_delta)
            .limit(limit)
        )
    ).all()

    return TeamListResponse(
        total_count=total_count, results=[_to_team_response(t) for t in teams]
    )


#############################################
#              GET TEAM BY ID               #
#############################################
@teams_router.get(
    "/teams/{team_id}",
    response_model=TeamResponse,
    summary="Get a team — admins or that team's own agents only",
)
async def get_team(
    team_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> TeamResponse:
    team = await db.get(Team, team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team not found."
        )

    if not _is_admin(current_user):
        requester_agent = await _get_agent_for_user(db, current_user.id)
        if not requester_agent or requester_agent.team_id != team_id:
            # 404, not 403 — don't confirm a team exists to non-members.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Team not found."
            )

    return _to_team_response(team)


#############################################
#                UPDATE TEAM                #
#############################################
@teams_router.patch(
    "/teams/{team_id}",
    response_model=TeamResponse,
    summary="Update a team's name/description (owner or admin only)",
)
async def update_team(
    team_id: int,
    payload: TeamUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> TeamResponse:
    team = await db.get(Team, team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team not found."
        )

    requester_agent = await _get_agent_for_user(db, current_user.id)
    is_owner = (
        requester_agent is not None
        and requester_agent.team_id == team_id
        and requester_agent.role == AgentRole.OWNER
    )
    if not (_is_admin(current_user) or is_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the team's owner or an admin can update this team.",
        )

    incoming_data = payload.model_dump(exclude_unset=True)
    if not incoming_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No parameters supplied."
        )

    incoming_data["date_modified"] = datetime.now(timezone.utc)
    incoming_data["modified_by"] = current_user.id

    team.sqlmodel_update(incoming_data)
    db.add(team)
    await db.commit()
    await db.refresh(team)

    return _to_team_response(team)


###########################################################
#   TEAM ROSTER — the team-scoped visibility requirement:  #
#   only that team's own agents (or an admin) can see who  #
#   is assigned to it.                                     #
###########################################################
@teams_router.get(
    "/teams/{team_id}/agents",
    response_model=AgentListResponse,
    summary="List a team's agents — visible only to that team's own members",
)
async def list_team_agents(
    team_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> AgentListResponse:
    team = await db.get(Team, team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team not found."
        )

    if not _is_admin(current_user):
        requester_agent = await _get_agent_for_user(db, current_user.id)
        if not requester_agent or requester_agent.team_id != team_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Team not found."
            )

    offset_delta = (page - 1) * limit
    total_count = (
        await db.exec(select(func.count(Agent.id)).where(Agent.team_id == team_id))
    ).one()
    agents = (
        await db.exec(
            select(Agent)
            .where(Agent.team_id == team_id)
            .order_by(Agent.date_created.asc())
            .offset(offset_delta)
            .limit(limit)
        )
    ).all()

    return AgentListResponse(
        total_count=total_count, results=[_to_agent_response(a) for a in agents]
    )


#############################################
#                UPDATE AGENT               #
#############################################
@teams_router.patch(
    "/agents/{agent_id}",
    response_model=AgentResponse,
    summary="Update an agent's extension (self, team owner, or admin)",
)
async def update_agent(
    agent_id: int,
    payload: AgentUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> AgentResponse:
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found."
        )

    is_self = agent.user_id == current_user.id
    requester_agent = await _get_agent_for_user(db, current_user.id)
    is_owner = (
        requester_agent is not None
        and requester_agent.team_id == agent.team_id
        and requester_agent.role == AgentRole.OWNER
    )
    if not (is_self or is_owner or _is_admin(current_user)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own agent record.",
        )

    incoming_data = payload.model_dump(exclude_unset=True)
    if not incoming_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No parameters supplied."
        )

    incoming_data["date_modified"] = datetime.now(timezone.utc)
    incoming_data["modified_by"] = current_user.id

    agent.sqlmodel_update(incoming_data)
    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    return _to_agent_response(agent)


#############################################
#                REMOVE AGENT               #
#############################################
@teams_router.delete(
    "/agents/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an agent from their team (owner or admin only)",
)
async def delete_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """The team's OWNER can't be removed through this endpoint — transfer
    ownership (via update_agent's role, or a future dedicated transfer
    endpoint) before removing the founding agent."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found."
        )

    requester_agent = await _get_agent_for_user(db, current_user.id)
    is_owner = (
        requester_agent is not None
        and requester_agent.team_id == agent.team_id
        and requester_agent.role == AgentRole.OWNER
    )
    if not (_is_admin(current_user) or is_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the team's owner or an admin can remove agents.",
        )

    if agent.role == AgentRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transfer ownership before removing the team's owner.",
        )

    await db.delete(agent)
    await db.commit()

    return None
