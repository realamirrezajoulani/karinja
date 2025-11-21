from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select, and_, or_, not_
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError

from dependencies import get_session, require_roles
from utilities.authentication import oauth2_scheme
from utilities.enumerables import LogicalOperator, UserRole

from models.relational_models import Comment, User  # assumes Comment model exists
from schemas.relational_schemas import RelationalCommentPublic
from schemas.comment import CommentCreate, CommentUpdate  # assumes these schemas exist

router = APIRouter()


@router.get(
    "/comments/",
    response_model=List[RelationalCommentPublic],
)
async def list_comments(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=200),
    # Allow all authenticated roles to call; internal logic enforces visibility.
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
    List comments with role-based visibility:
    - FULL_ADMIN: sees all comments.
    - ADMIN: sees:
        * all comments authored by EMPLOYER or JOB_SEEKER (moderation access),
        * plus their own comments.
    - EMPLOYER / JOB_SEEKER: sees only their own comments (they cannot view other users' comments in this endpoint).
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    base_query = select(Comment).order_by(Comment.created_at.desc())

    if requester_role == UserRole.FULL_ADMIN.value:
        query = base_query
    elif requester_role == UserRole.ADMIN.value:
        # Admin sees comments authored by EMPLOYER/JOB_SEEKER OR their own comments.
        allowed_author_roles = [UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value]
        # Join-free approach: filter by comment.user.role is not directly accessible here;
        # we filter by two cases:
        # 1) comment.user_id == requester_id  (own comments)
        # 2) comment authored by users whose role is EMPLOYER or JOB_SEEKER
        # To express (2) without join, we assume Comment has relationship to User and DB supports subquery.
        # Simpler & robust: perform an explicit subquery to fetch user ids with allowed roles.
        subq = select(User.id).where(User.role.in_(allowed_author_roles))
        query = base_query.where(
            or_(
                Comment.user_id == requester_id,
                Comment.user_id.in_(subq),
            )
        )
    elif requester_role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
        # Regular users see only their own comments
        query = base_query.where(Comment.user_id == requester_id)
    else:
        raise HTTPException(status_code=403, detail="Invalid role")

    query = query.offset(offset).limit(limit)
    result = await session.exec(query)
    return result.all()


@router.post(
    "/comments/",
    response_model=RelationalCommentPublic,
)
async def create_comment(
    *,
    session: AsyncSession = Depends(get_session),
    comment_create: CommentCreate,
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
    Create a comment.
    - EMPLOYER and JOB_SEEKER: allowed to create comments.
    - ADMIN and FULL_ADMIN: allowed to create comments as well.
    """
    requester_id = _user["id"]
    requester_role = _user["role"]

    # Validate minimal content
    if not getattr(comment_create, "content", None) or not comment_create.content.strip():
        raise HTTPException(status_code=400, detail="Comment content is required")

    try:
        db_comment = Comment(
            content=comment_create.content,
            blog_id=comment_create.blog_id,
            user_id=requester_id,  # set author as requester
            is_approved=getattr(comment_create, "is_approved", None),
            is_spam=False,
        )
        session.add(db_comment)
        await session.commit()
        await session.refresh(db_comment)
        return db_comment
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Could not create comment due to data conflict")
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating comment: {e}")


@router.get(
    "/comments/{comment_id}",
    response_model=RelationalCommentPublic,
)
async def get_comment(
    *,
    session: AsyncSession = Depends(get_session),
    comment_id: UUID,
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
    Retrieve a single comment with role-based visibility:
    - FULL_ADMIN: can view any comment.
    - ADMIN: can view comments authored by EMPLOYER/JOB_SEEKER OR their own comments.
    - EMPLOYER / JOB_SEEKER: can view only their own comments.
    """
    requester_role = _user["role"]
    requester_id_str = str(_user["id"])

    # fetch comment
    result = await session.exec(select(Comment).where(Comment.id == comment_id))
    comment = result.one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    author_id_str = str(comment.user_id)

    if requester_role == UserRole.FULL_ADMIN.value:
        pass  # full access
    elif requester_role == UserRole.ADMIN.value:
        # Admin can view if comment author is EMPLOYER/JOB_SEEKER or admin's own comment
        # To know author's role, we need to fetch the user record
        author = await session.get(User, comment.user_id)
        if author is None:
            # if user missing, deny for safety
            raise HTTPException(status_code=404, detail="Comment author not found")
        if author.role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
            pass  # admin can view these
        elif author_id_str == requester_id_str:
            pass  # admin viewing their own comment
        else:
            raise HTTPException(status_code=403, detail="Admin can only view own or Employer/JobSeeker comments")
    elif requester_role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
        # can view only their own comments
        if author_id_str != requester_id_str:
            raise HTTPException(status_code=403, detail="You can view only your own comments")
    else:
        raise HTTPException(status_code=403, detail="Invalid role")

    return comment


@router.patch(
    "/comments/{comment_id}",
    response_model=RelationalCommentPublic,
)
async def patch_comment(
    *,
    session: AsyncSession = Depends(get_session),
    comment_id: UUID,
    comment_update: CommentUpdate,
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
    Update a comment.
    - FULL_ADMIN: can update any comment.
    - ADMIN: can update comments authored by EMPLOYER/JOB_SEEKER, and their own comments.
             cannot update other admins' comments.
    - EMPLOYER / JOB_SEEKER: can update only their own comments.
    """
    requester_role = _user["role"]
    requester_id_str = str(_user["id"])

    result = await session.exec(select(Comment).where(Comment.id == comment_id))
    target_comment = result.one_or_none()
    if not target_comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    author = await session.get(User, target_comment.user_id)
    if author is None:
        raise HTTPException(status_code=404, detail="Comment author not found")
    author_role = author.role
    author_id_str = str(author.id)

    # Permission checks
    if requester_role == UserRole.FULL_ADMIN.value:
        pass  # full permission
    elif requester_role == UserRole.ADMIN.value:
        # Admin may edit their own comments or comments of Employer/JobSeeker
        if author_id_str == requester_id_str:
            pass  # editing own comment
        elif author_role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
            pass  # allowed to moderate these comments
        else:
            # cannot edit other admins' or full_admin's comments
            raise HTTPException(status_code=403, detail="Admin cannot edit this comment")
    elif requester_role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
        # can only edit own comments
        if author_id_str != requester_id_str:
            raise HTTPException(status_code=403, detail="You can edit only your own comments")
    else:
        raise HTTPException(status_code=403, detail="Invalid role")

    update_data = comment_update.model_dump(exclude_unset=True)

    # Prevent non-FULL_ADMIN from changing the comment's author
    if "user_id" in update_data and requester_role != UserRole.FULL_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only FULL_ADMIN can change comment author")

    # Apply updates
    for field, value in update_data.items():
        setattr(target_comment, field, value)

    await session.commit()
    await session.refresh(target_comment)
    return target_comment


@router.delete(
    "/comments/{comment_id}",
    response_model=dict[str, str],
)
async def delete_comment(
    *,
    session: AsyncSession = Depends(get_session),
    comment_id: UUID,
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
    Delete a comment.
    - FULL_ADMIN: can delete any comment.
    - ADMIN: can delete their own comments or comments authored by EMPLOYER/JOB_SEEKER.
    - EMPLOYER / JOB_SEEKER: can delete only their own comments.
    """
    requester_role = _user["role"]
    requester_id_str = str(_user["id"])

    result = await session.exec(select(Comment).where(Comment.id == comment_id))
    target_comment = result.one_or_none()
    if not target_comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    author = await session.get(User, target_comment.user_id)
    if author is None:
        raise HTTPException(status_code=404, detail="Comment author not found")
    author_role = author.role
    author_id_str = str(author.id)

    # Permission checks
    if requester_role == UserRole.FULL_ADMIN.value:
        pass
    elif requester_role == UserRole.ADMIN.value:
        if author_id_str == requester_id_str:
            pass  # can delete own comment
        elif author_role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
            pass  # can delete comments by Employer/JobSeeker
        else:
            raise HTTPException(status_code=403, detail="Admin cannot delete this comment")
    elif requester_role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
        if author_id_str != requester_id_str:
            raise HTTPException(status_code=403, detail="You can delete only your own comments")
    else:
        raise HTTPException(status_code=403, detail="Invalid role")

    await session.delete(target_comment)
    await session.commit()
    return {"msg": "Comment successfully deleted"}


@router.get(
    "/comments/search/",
    response_model=List[RelationalCommentPublic],
)
async def search_comments(
    *,
    session: AsyncSession = Depends(get_session),
    # Allowed search fields
    content: str | None = None,
    blog_id: UUID | None = None,
    user_id: UUID | None = None,
    is_approved: bool | None = None,
    is_spam: bool | None = None,

    # role/auth
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
    Search comments using logical operator (AND / OR / NOT).

    Searchable fields: content, blog_id, user_id, is_approved, is_spam.

    Access rules:
    - FULL_ADMIN: can search across all comments.
    - ADMIN: can search comments written by EMPLOYER/JOB_SEEKER + their own.
    - EMPLOYER / JOB_SEEKER: can search only their own comments.
    """
    requester_role = _user["role"]
    requester_id_str = str(_user["id"])

    # Build conditions
    conditions = []
    if content:
        conditions.append(Comment.content.ilike(f"%{content}%"))
    if blog_id:
        conditions.append(Comment.blog_id == blog_id)
    if user_id:
        conditions.append(Comment.user_id == user_id)
    if is_approved is not None:
        conditions.append(Comment.is_approved == is_approved)
    if is_spam is not None:
        conditions.append(Comment.is_spam == is_spam)

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

    # Role-based filtering
    if requester_role == UserRole.FULL_ADMIN.value:
        # full unrestricted search
        final_where = where_clause

    elif requester_role == UserRole.ADMIN.value:
        # Admin can see:
        #   - their own comments
        #   - comments written by employer/job_seeker
        allowed_roles = [UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value]
        subq = select(User.id).where(User.role.in_(allowed_roles))

        final_where = and_(
            where_clause,
            or_(
                Comment.user_id == requester_id_str,
                Comment.user_id.in_(subq)
            )
        )

    elif requester_role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
        # regular users → only their own comments
        final_where = and_(where_clause, Comment.user_id == requester_id_str)

    else:
        raise HTTPException(status_code=403, detail="Invalid role")

    # Execute query
    query = select(Comment).where(final_where).offset(offset).limit(limit)
    result = await session.exec(query)
    return result.all()
