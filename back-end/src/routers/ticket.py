from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select, and_, or_, not_
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError

from dependencies import get_session, require_roles
from utilities.authentication import oauth2_scheme
from utilities.enumerables import LogicalOperator, TicketPriority, TicketStatus, TicketType, UserRole

from models.relational_models import Ticket, User
from schemas.relational_schemas import RelationalTicketPublic
from schemas.ticket import TicketCreate, TicketUpdate

router = APIRouter()


@router.get(
    "/tickets/",
    response_model=List[RelationalTicketPublic],
)
async def list_tickets(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=200),
    _user: dict = Depends(
        require_roles(
            UserRole.FULL_ADMIN.value,
            UserRole.ADMIN.value,
            UserRole.EMPLOYER.value,
            UserRole.JOB_SEEKER.value,
        )
    ),
    _: str = Depends(oauth2_scheme),
):
    """
    List tickets with role-based visibility:
    - FULL_ADMIN: sees all tickets.
    - ADMIN: sees tickets they authored AND tickets authored by EMPLOYER/JOB_SEEKER (moderation).
    - EMPLOYER / JOB_SEEKER: sees only their own tickets.
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    base_query = select(Ticket).order_by(Ticket.created_at.desc())

    if requester_role == UserRole.FULL_ADMIN.value:
        query = base_query
    elif requester_role == UserRole.ADMIN.value:
        # Admin sees own tickets or tickets authored by EMPLOYER/JOB_SEEKER
        allowed_roles = [UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value]
        subq = select(User.id).where(User.role.in_(allowed_roles))
        query = base_query.where(or_(Ticket.requester_user_id == requester_id, Ticket.requester_user_id.in_(subq)))
    elif requester_role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
        # Regular users see only their own tickets
        query = base_query.where(Ticket.requester_user_id == requester_id)
    else:
        raise HTTPException(status_code=403, detail="Invalid role")

    query = query.offset(offset).limit(limit)
    result = await session.exec(query)
    return result.all()


@router.post(
    "/tickets/",
    response_model=RelationalTicketPublic,
)
async def create_ticket(
    *,
    session: AsyncSession = Depends(get_session),
    ticket_create: TicketCreate,
    _user: dict = Depends(
        require_roles(
            UserRole.FULL_ADMIN.value,
            UserRole.ADMIN.value,
            UserRole.EMPLOYER.value,
            UserRole.JOB_SEEKER.value,
        )
    ),
    _: str = Depends(oauth2_scheme),
):
    """
    Create a new ticket.
    - All roles (FULL_ADMIN, ADMIN, EMPLOYER, JOB_SEEKER) can create tickets.
    - The ticket requester_user_id is set to the authenticated user automatically.
    """
    requester_id = _user["id"]

    # Basic validation
    if not getattr(ticket_create, "subject", None) or not ticket_create.subject.strip():
        raise HTTPException(status_code=400, detail="Subject is required")

    try:
        db_ticket = Ticket(
            subject=ticket_create.subject,
            description=getattr(ticket_create, "description", None),
            status=getattr(ticket_create, "status", TicketStatus.OPEN.value),
            ticket_type=getattr(ticket_create, "ticket_type", TicketType.QUESTION.value),
            priority=getattr(ticket_create, "priority", TicketPriority.MEDIUM.value),
            answer=getattr(ticket_create, "answer", None),
            image_url=getattr(ticket_create, "image_url", None),
            requester_user_id=requester_id,
        )
        session.add(db_ticket)
        await session.commit()
        await session.refresh(db_ticket)
        return db_ticket
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Ticket could not be created due to data conflict")
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating ticket: {e}")


@router.get(
    "/tickets/{ticket_id}",
    response_model=RelationalTicketPublic,
)
async def get_ticket(
    *,
    session: AsyncSession = Depends(get_session),
    ticket_id: UUID,
    _user: dict = Depends(
        require_roles(
            UserRole.FULL_ADMIN.value,
            UserRole.ADMIN.value,
            UserRole.EMPLOYER.value,
            UserRole.JOB_SEEKER.value,
        )
    ),
    _: str = Depends(oauth2_scheme),
):
    """
    Retrieve a single ticket with role-based visibility:
    - FULL_ADMIN: can view any ticket.
    - ADMIN: can view their own tickets and tickets authored by EMPLOYER/JOB_SEEKER.
    - EMPLOYER / JOB_SEEKER: can view only their own tickets.
    """
    requester_role = _user["role"]
    requester_id_str = str(_user["id"])

    result = await session.exec(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    author_id_str = str(ticket.requester_user_id)
    if requester_role == UserRole.FULL_ADMIN.value:
        pass
    elif requester_role == UserRole.ADMIN.value:
        # Admin may view own tickets or tickets by Employer/JobSeeker
        if author_id_str == requester_id_str:
            pass
        else:
            author = await session.get(User, ticket.requester_user_id)
            if not author:
                raise HTTPException(status_code=404, detail="Ticket owner not found")
            if author.role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
                pass
            else:
                raise HTTPException(status_code=403, detail="Admin can only view their own tickets or those by Employer/JobSeeker")
    elif requester_role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
        if author_id_str != requester_id_str:
            raise HTTPException(status_code=403, detail="You can view only your own tickets")
    else:
        raise HTTPException(status_code=403, detail="Invalid role")

    return ticket


@router.patch(
    "/tickets/{ticket_id}",
    response_model=RelationalTicketPublic,
)
async def patch_ticket(
    *,
    session: AsyncSession = Depends(get_session),
    ticket_id: UUID,
    ticket_update: TicketUpdate,
    _user: dict = Depends(
        require_roles(
            UserRole.FULL_ADMIN.value,
            UserRole.ADMIN.value,
            UserRole.EMPLOYER.value,
            UserRole.JOB_SEEKER.value,
        )
    ),
    _: str = Depends(oauth2_scheme),
):
    """
    Update a ticket.
    - FULL_ADMIN: can update any ticket.
    - ADMIN: can update only tickets they authored.
    - EMPLOYER / JOB_SEEKER: can update only their own tickets.
    """
    requester_role = _user["role"]
    requester_id_str = str(_user["id"])

    result = await session.exec(select(Ticket).where(Ticket.id == ticket_id))
    target_ticket = result.one_or_none()
    if not target_ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    author_id_str = str(target_ticket.requester_user_id)

    if requester_role == UserRole.FULL_ADMIN.value:
        pass
    elif requester_role == UserRole.ADMIN.value:
        if author_id_str != requester_id_str:
            raise HTTPException(status_code=403, detail="Admin can only edit tickets they authored")
    elif requester_role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
        if author_id_str != requester_id_str:
            raise HTTPException(status_code=403, detail="You can edit only your own tickets")
    else:
        raise HTTPException(status_code=403, detail="Invalid role")

    update_data = ticket_update.model_dump(exclude_unset=True)

    # Prevent non-FULL_ADMIN from reassigning requester_user_id
    if "requester_user_id" in update_data and requester_role != UserRole.FULL_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only FULL_ADMIN can change ticket owner")

    # Apply updates
    for field, value in update_data.items():
        setattr(target_ticket, field, value)

    await session.commit()
    await session.refresh(target_ticket)
    return target_ticket


@router.delete(
    "/tickets/{ticket_id}",
    response_model=dict[str, str],
)
async def delete_ticket(
    *,
    session: AsyncSession = Depends(get_session),
    ticket_id: UUID,
    _user: dict = Depends(
        require_roles(
            UserRole.FULL_ADMIN.value,
            UserRole.ADMIN.value,
            UserRole.EMPLOYER.value,
            UserRole.JOB_SEEKER.value,
        )
    ),
    _: str = Depends(oauth2_scheme),
):
    """
    Delete a ticket.
    - FULL_ADMIN: can delete any ticket.
    - ADMIN: can delete only tickets they authored.
    - EMPLOYER / JOB_SEEKER: can delete only their own tickets.
    """
    requester_role = _user["role"]
    requester_id_str = str(_user["id"])

    result = await session.exec(select(Ticket).where(Ticket.id == ticket_id))
    target_ticket = result.one_or_none()
    if not target_ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    author_id_str = str(target_ticket.requester_user_id)

    if requester_role == UserRole.FULL_ADMIN.value:
        pass
    elif requester_role == UserRole.ADMIN.value:
        if author_id_str != requester_id_str:
            raise HTTPException(status_code=403, detail="Admin can only delete tickets they authored")
    elif requester_role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
        if author_id_str != requester_id_str:
            raise HTTPException(status_code=403, detail="You can delete only your own tickets")
    else:
        raise HTTPException(status_code=403, detail="Invalid role")

    await session.delete(target_ticket)
    await session.commit()
    return {"msg": "Ticket successfully deleted"}


@router.get(
    "/tickets/search/",
    response_model=List[RelationalTicketPublic],
)
async def search_tickets(
    *,
    session: AsyncSession = Depends(get_session),
    # searchable fields
    subject: str | None = None,
    description: str | None = None,
    status: TicketStatus | None = None,
    ticket_type: TicketType | None = None,
    priority: TicketPriority | None = None,
    requester_user_id: UUID | None = None,
    answer: str | None = None,
    image_url: str | None = None,

    _user: dict = Depends(
        require_roles(
            UserRole.FULL_ADMIN.value,
            UserRole.ADMIN.value,
            UserRole.EMPLOYER.value,
            UserRole.JOB_SEEKER.value,
        )
    ),
    operator: LogicalOperator = Query(...),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=200),
    _: str = Depends(oauth2_scheme),
):
    """
    Search tickets using logical operator (AND / OR / NOT).
    - FULL_ADMIN: search across all tickets.
    - ADMIN: can search their own tickets and tickets by Employer/JobSeeker.
    - EMPLOYER / JOB_SEEKER: can search only their own tickets.
    """
    requester_role = _user["role"]
    requester_id_str = str(_user["id"])

    # Build conditions
    conditions = []
    if subject:
        conditions.append(Ticket.subject.ilike(f"%{subject}%"))
    if description:
        conditions.append(Ticket.description.ilike(f"%{description}%"))
    if status:
        conditions.append(Ticket.status == status.value)
    if ticket_type:
        conditions.append(Ticket.ticket_type == ticket_type.value)
    if priority:
        conditions.append(Ticket.priority == priority.value)
    if requester_user_id:
        conditions.append(Ticket.requester_user_id == requester_user_id)
    if answer:
        conditions.append(Ticket.answer.ilike(f"%{answer}%"))
    if image_url:
        conditions.append(Ticket.image_url.ilike(f"%{image_url}%"))

    if not conditions:
        raise HTTPException(status_code=400, detail="No search parameters provided")

    # Combine conditions
    if operator == LogicalOperator.AND:
        where_clause = and_(*conditions)
    elif operator == LogicalOperator.OR:
        where_clause = or_(*conditions)
    elif operator == LogicalOperator.NOT:
        where_clause = not_(or_(*conditions))
    else:
        raise HTTPException(status_code=400, detail="Invalid logical operator")

    # Role-based visibility
    if requester_role == UserRole.FULL_ADMIN.value:
        final_where = where_clause
    elif requester_role == UserRole.ADMIN.value:
        # Admin: own tickets OR tickets authored by Employer/JobSeeker
        allowed_roles = [UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value]
        subq = select(User.id).where(User.role.in_(allowed_roles))
        final_where = and_(where_clause, or_(Ticket.requester_user_id == requester_id_str, Ticket.requester_user_id.in_(subq)))
    elif requester_role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
        # regular users -> only their own tickets
        final_where = and_(where_clause, Ticket.requester_user_id == requester_id_str)
    else:
        raise HTTPException(status_code=403, detail="Invalid role")

    query = select(Ticket).where(final_where).offset(offset).limit(limit)
    result = await session.exec(query)
    return result.all()
