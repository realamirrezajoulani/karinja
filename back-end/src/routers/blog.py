# Source file (for reference): /mnt/data/New Text Document.txt
from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select, and_, or_, not_
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError

from dependencies import get_session, require_roles
from utilities.authentication import oauth2_scheme
from utilities.enumerables import LogicalOperator, BlogStatus, UserRole

from models.relational_models import Blog
from schemas.relational_schemas import RelationalBlogPublic
from schemas.blog import BlogCreate, BlogUpdate

router = APIRouter()


@router.get(
    "/blogs/",
    response_model=List[RelationalBlogPublic],
)
async def get_blogs(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    # Require any authenticated role that can list blogs.
    _user: dict = Depends(
        require_roles(
            UserRole.FULL_ADMIN.value,
            UserRole.ADMIN.value,
            UserRole.EMPLOYER.value,
            UserRole.JOB_SEEKER.value,
        )
    ),
    # Ensure the caller is authenticated (token required)
    _: str = Depends(oauth2_scheme),
):
    """
    List blogs with role-based visibility:
    - FULL_ADMIN: sees all blogs.
    - ADMIN: sees all blogs.
    - EMPLOYER / JOB_SEEKER: sees only PUBLISHED blogs.
    """
    requester_role = _user["role"]

    # Base query ordered by newest first
    query = select(Blog).order_by(Blog.created_at.desc())

    # Apply visibility rules
    if requester_role == UserRole.FULL_ADMIN.value:
        pass  # full access
    elif requester_role == UserRole.ADMIN.value:
        pass  # admin sees all blogs
    elif requester_role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
        # non-admins only see published posts
        query = query.where(Blog.status == BlogStatus.PUBLISHED.value)
    else:
        raise HTTPException(status_code=403, detail="Invalid role")

    query = query.offset(offset).limit(limit)
    result = await session.exec(query)
    return result.all()


@router.post(
    "/blogs/",
    response_model=RelationalBlogPublic,
)
async def create_blog(
    *,
    session: AsyncSession = Depends(get_session),
    blog_create: BlogCreate,
    _user: dict = Depends(
        # Only FULL_ADMIN and ADMIN can create blogs
        require_roles(
            UserRole.FULL_ADMIN.value,
            UserRole.ADMIN.value,
        )
    ),
    _: str = Depends(oauth2_scheme),
):
    """
    Create a new blog post.
    Access rules:
    - FULL_ADMIN / ADMIN: may create posts and set status.
    - EMPLOYER / JOB_SEEKER: not allowed to create posts.
    """
    requester_role = _user["role"]
    requester_id = _user["id"]

    # Admins may set any status; default to DRAFT if not provided.
    incoming_status = getattr(blog_create, "status", None)
    status_to_set = incoming_status or BlogStatus.DRAFT.value

    try:
        db_blog = Blog(
            title=blog_create.title,
            content=blog_create.content,
            excerpt=getattr(blog_create, "excerpt", None),
            status=status_to_set,
            author_user_id=requester_id,
            published_at=getattr(blog_create, "published_at", None),
        )
        session.add(db_blog)
        await session.commit()
        await session.refresh(db_blog)
        return db_blog

    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Blog could not be created due to data conflict")
    except Exception as e:
        await session.rollback()
        # Prefer logging in real app; return safe message here.
        raise HTTPException(status_code=500, detail=f"Error creating blog: {e}")


@router.get(
    "/blogs/{blog_id}",
    response_model=RelationalBlogPublic,
)
async def get_blog(
    *,
    session: AsyncSession = Depends(get_session),
    blog_id: UUID,
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
    Retrieve a single blog post with role-based visibility:
    - FULL_ADMIN / ADMIN: can view any blog.
    - EMPLOYER / JOB_SEEKER: can view only PUBLISHED blogs.
    """
    requester_role = _user["role"]

    query = select(Blog).where(Blog.id == blog_id)

    if requester_role in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value):
        pass  # full access
    elif requester_role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
        query = query.where(Blog.status == BlogStatus.PUBLISHED.value)
    else:
        raise HTTPException(status_code=403, detail="Invalid role")

    result = await session.exec(query)
    blog = result.one_or_none()
    if not blog:
        raise HTTPException(status_code=404, detail="Blog not found")

    return blog


@router.patch(
    "/blogs/{blog_id}",
    response_model=RelationalBlogPublic,
)
async def patch_blog(
    *,
    session: AsyncSession = Depends(get_session),
    blog_id: UUID,
    blog_update: BlogUpdate,
    _user: dict = Depends(
        # Both FULL_ADMIN and ADMIN can reach this endpoint, but ADMIN is restricted below.
        require_roles(
            UserRole.FULL_ADMIN.value,
            UserRole.ADMIN.value,
        )
    ),
    _: str = Depends(oauth2_scheme),
):
    """
    Update a blog post.
    Rules:
    - FULL_ADMIN: can update any blog.
    - ADMIN: can update only blogs they authored.
    - EMPLOYER / JOB_SEEKER: cannot update (they don't have access to this endpoint).
    """
    result = await session.exec(select(Blog).where(Blog.id == blog_id))
    target_blog = result.one_or_none()
    if not target_blog:
        raise HTTPException(status_code=404, detail="Blog not found")

    requester_role = _user["role"]
    requester_id_str = str(_user["id"])
    author_id_str = str(target_blog.author_user_id)

    # Permission enforcement:
    if requester_role == UserRole.FULL_ADMIN.value:
        # full permission
        pass
    elif requester_role == UserRole.ADMIN.value:
        # Admins can only modify their own blogs
        if author_id_str != requester_id_str:
            raise HTTPException(status_code=403, detail="Admin can only edit blogs they authored")
    else:
        # Shouldn't reach here due to require_roles, but safe-guard
        raise HTTPException(status_code=403, detail="Invalid role")

    update_data = blog_update.model_dump(exclude_unset=True)

    # Optional: prevent admins from changing certain critical fields (example)
    # If you want admins restricted from changing 'author_user_id' or similar, enforce here.
    if "author_user_id" in update_data:
        # Prevent changing the author unless FULL_ADMIN
        if requester_role != UserRole.FULL_ADMIN.value:
            raise HTTPException(status_code=403, detail="Only FULL_ADMIN can change the author")

    # Apply updates to the target_blog
    for field, value in update_data.items():
        setattr(target_blog, field, value)

    await session.commit()
    await session.refresh(target_blog)
    return target_blog


@router.delete(
    "/blogs/{blog_id}",
    response_model=dict[str, str],
)
async def delete_blog(
    *,
    session: AsyncSession = Depends(get_session),
    blog_id: UUID,
    _user: dict = Depends(
        # Both FULL_ADMIN and ADMIN can reach this endpoint, but ADMIN is restricted below.
        require_roles(
            UserRole.FULL_ADMIN.value,
            UserRole.ADMIN.value,
        )
    ),
    _: str = Depends(oauth2_scheme),
):
    """
    Delete a blog post.
    Rules:
    - FULL_ADMIN: can delete any blog.
    - ADMIN: can delete only blogs they authored.
    """
    result = await session.exec(select(Blog).where(Blog.id == blog_id))
    target_blog = result.one_or_none()
    if not target_blog:
        raise HTTPException(status_code=404, detail="Blog not found")

    requester_role = _user["role"]
    requester_id_str = str(_user["id"])
    author_id_str = str(target_blog.author_user_id)

    if requester_role == UserRole.FULL_ADMIN.value:
        pass  # full permission
    elif requester_role == UserRole.ADMIN.value:
        if author_id_str != requester_id_str:
            raise HTTPException(status_code=403, detail="Admin can only delete blogs they authored")
    else:
        raise HTTPException(status_code=403, detail="Invalid role")

    await session.delete(target_blog)
    await session.commit()
    return {"msg": "Blog successfully deleted"}


@router.get(
    "/blogs/search/",
    response_model=List[RelationalBlogPublic],
)
async def search_blogs(
    *,
    session: AsyncSession = Depends(get_session),
    title: str | None = None,
    content: str | None = None,
    author_id: UUID | None = None,
    status: BlogStatus | None = None,
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
    limit: int = Query(default=100, le=100),
    _: str = Depends(oauth2_scheme),
):
    """
    Search blogs using a logical operator (AND / OR / NOT).
    - FULL_ADMIN: search across all blogs.
    - ADMIN: search across all blogs.
    - EMPLOYER / JOB_SEEKER: results limited to PUBLISHED blogs only.
    """
    requester_role = _user["role"]

    # Build search conditions from provided params
    conditions = []
    if title:
        conditions.append(Blog.title.ilike(f"%{title}%"))
    if content:
        conditions.append(Blog.content.ilike(f"%{content}%"))
    if author_id:
        conditions.append(Blog.author_user_id == author_id)
    if status:
        conditions.append(Blog.status == status.value)

    if not conditions:
        raise HTTPException(status_code=400, detail="No search parameters provided")

    # Combine conditions with the requested logical operator
    if operator == LogicalOperator.AND:
        where_clause = and_(*conditions)
    elif operator == LogicalOperator.OR:
        where_clause = or_(*conditions)
    elif operator == LogicalOperator.NOT:
        where_clause = not_(or_(*conditions))
    else:
        raise HTTPException(status_code=400, detail="Invalid logical operator")

    # Apply role-based restrictions on top of search criteria
    if requester_role in (UserRole.FULL_ADMIN.value, UserRole.ADMIN.value):
        final_where = where_clause
    elif requester_role in (UserRole.EMPLOYER.value, UserRole.JOB_SEEKER.value):
        final_where = and_(where_clause, Blog.status == BlogStatus.PUBLISHED.value)
    else:
        raise HTTPException(status_code=403, detail="Invalid role")

    query = select(Blog).where(final_where).offset(offset).limit(limit)
    result = await session.exec(query)
    blogs = result.all()
    return blogs
