from typing import Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import EmailStr
from datetime import datetime

from dependencies import get_session, require_roles
from sqlmodel.ext.asyncio.session import AsyncSession

from models.relational_models import User
from schemas.relational_schemas import RelationalUserPublic
from sqlmodel import SQLModel, and_, func, not_, or_, select
from sqlalchemy.exc import IntegrityError

from utilities.enumerables import UserRole
from utilities.authentication import oauth2_scheme
from models import relational_models


router = APIRouter()


class TopItem(SQLModel):
    key: str | None
    count: int


class AdvancedStatsResponse(SQLModel):
    totals: dict[str, int]
    applications_by_status: list[TopItem]
    top_skills: list[TopItem]
    applications_per_posting: dict[str, Any]
    average_time_to_first_application_days: float | None = None
    resumes_by_visibility: list[TopItem]
    applicants_by_province: list[TopItem]
    education_degree_distribution: list[TopItem]


# ---------- endpoint -----------------------------
@router.get(
    "/advanced",
    response_model=AdvancedStatsResponse,
)
async def get_advanced_statistics(
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    # Only ADMIN and FULL_ADMIN can call this endpoint
    _user: dict = Depends(
        require_roles(
            UserRole.FULL_ADMIN.value,
            UserRole.ADMIN.value,
        )
    ),
    # ensure caller is authenticated (token required)
    _: str = Depends(oauth2_scheme),

    # analytical filters (Query-style like your get_users)
    date_from: datetime | None = Query(None, description="Start date (inclusive) - created_at"),
    date_to: datetime | None = Query(None, description="End date (inclusive) - created_at"),
    company_id: str | None = Query(None, description="Limit stats to a specific company_id (UUID)"),
    top_n: int = Query(10, gt=0, le=100, description="How many top items to return"),
):
    """
    Return advanced statistics (totals, application status distribution, top skills, etc).
    - FULL_ADMIN: sees global stats
    - ADMIN: results are limited to their company (or to the provided company_id)
    """

    requester_role = _user["role"]

    # If caller is ADMIN and company_id not provided, limit to caller's company
    if requester_role == UserRole.ADMIN.value and company_id is None:
        # assume caller's company_id is present in the _user payload
        company_id = _user.get("company_id")

    # Build a list of filter lambdas and a helper to apply them
    where_clauses = []

    if date_from:
        where_clauses.append(lambda model: model.created_at >= date_from)
    if date_to:
        where_clauses.append(lambda model: model.created_at <= date_to)
    if company_id:
        # Some models have company_id; for others a join-filter will be applied where appropriate.
        pass

    def apply_filters(stmt, model):
        for f in where_clauses:
            stmt = stmt.where(f(model))
        # If the model itself has company_id and a company_id is specified, apply it
        if company_id and hasattr(model, "company_id"):
            stmt = stmt.where(model.company_id == company_id)
        return stmt

    # ---------- 1) Totals ----------
    totals: dict[str, int] = {}

    q = select(func.count()).select_from(User)
    q = apply_filters(q, User)
    res = await session.exec(q)
    totals["total_users"] = int(res.one_or_none())

    q = select(func.count()).select_from(relational_models.Company)
    q = apply_filters(q, relational_models.Company)
    res = await session.exec(q)
    totals["total_companies"] = int(res.one_or_none())

    q = select(func.count()).select_from(relational_models.JobPosting)
    # apply_filters will add company filter if applicable
    q = apply_filters(q, relational_models.JobPosting)
    res = await session.exec(q)
    totals["total_job_postings"] = int(res.one_or_none())

    q = select(func.count()).select_from(relational_models.JobApplication)
    q = apply_filters(q, relational_models.JobApplication)
    res = await session.exec(q)
    totals["total_job_applications"] = int(res.one_or_none())

    q = select(func.count()).select_from(relational_models.JobSeekerResume)
    q = apply_filters(q, relational_models.JobSeekerResume)
    res = await session.exec(q)
    totals["total_resumes"] = int(res.one_or_none())

    # ---------- 2) Applications by status ----------
    q = select(relational_models.JobApplication.status, func.count().label("cnt")).group_by(relational_models.JobApplication.status)
    q = apply_filters(q, relational_models.JobApplication)
    res = await session.exec(q)
    applications_by_status = [TopItem(key=str(row[0]), count=int(row[1])) for row in res.all()]

    # ---------- 3) Top skills ----------
    q = (
        select(relational_models.JobSeekerSkill.title, func.count().label("cnt"))
        .group_by(relational_models.JobSeekerSkill.title)
        .order_by(func.count().desc())
        .limit(top_n)
    )
    q = apply_filters(q, relational_models.JobSeekerSkill)
    res = await session.exec(q)
    top_skills = [TopItem(key=row[0], count=int(row[1])) for row in res.all()]

    # Note on offset/limit: top_n controls the top lists; offset/limit params are kept for consistency
    # with your get_users style and can be applied to heavy lists if needed.

    # ---------- 4) Applications per posting (min/max/avg) ----------
    subq = (
        select(relational_models.JobApplication.job_posting_id, func.count().label("app_count"))
        .group_by(relational_models.JobApplication.job_posting_id)
    ).subquery()

    q = select(
        func.coalesce(func.min(subq.c.app_count), 0),
        func.coalesce(func.max(subq.c.app_count), 0),
        func.coalesce(func.avg(subq.c.app_count), 0).label("avg_apps"),
    )
    res = await session.exec(q)
    min_apps, max_apps, avg_apps = res.one()
    applications_per_posting = {
        "min": int(min_apps),
        "max": int(max_apps),
        "avg": float(avg_apps) if avg_apps is not None else 0.0,
    }

    # ---------- 5) Average time to first application (days) ----------
    # Note: this query uses PostgreSQL's date_part('epoch', ...). If you're using another DB
    # (e.g. SQLite or MySQL) adapt this part accordingly.
    average_time_to_first_application_days: float | None = None
    try:
        q = (
            select(func.avg(func.date_part('epoch', relational_models.JobApplication.created_at - relational_models.JobPosting.created_at)) / 86400.0)
            .select_from(relational_models.JobApplication)
            .join(relational_models.JobPosting, relational_models.JobApplication.job_posting_id == relational_models.JobPosting.id)
        )
        # If company_id is specified and JobPosting has company_id, apply it
        if company_id:
            q = q.where(relational_models.JobPosting.company_id == company_id)
        res = await session.exec(q)
        avg_days = res.one_or_none()
        average_time_to_first_application_days = float(avg_days) if avg_days is not None else None
    except Exception:
        # Fallback for DBs that don't support date_part or interval arithmetic the same way
        average_time_to_first_application_days = None

    # ---------- 6) Resumes by visibility ----------
    q = select(relational_models.JobSeekerResume.is_visible, func.count().label("cnt")).group_by(relational_models.JobSeekerResume.is_visible)
    q = apply_filters(q, relational_models.JobSeekerResume)
    res = await session.exec(q)
    resumes_by_visibility = [TopItem(key=str(row[0]), count=int(row[1])) for row in res.all()]

    # ---------- 7) Applicants by province ----------
    q = (
        select(relational_models.JobSeekerPersonalInformation.residence_province, func.count().label("cnt"))
        .group_by(relational_models.JobSeekerPersonalInformation.residence_province)
        .order_by(func.count().desc())
        .limit(top_n)
    )
    q = apply_filters(q, relational_models.JobSeekerPersonalInformation)
    res = await session.exec(q)
    applicants_by_province = [TopItem(key=str(row[0]), count=int(row[1])) for row in res.all()]

    # ---------- 8) Education degree distribution ----------
    q = (
        select(relational_models.JobSeekerEducation.degree, func.count().label("cnt"))
        .group_by(relational_models.JobSeekerEducation.degree)
        .order_by(func.count().desc())
        .limit(top_n)
    )
    q = apply_filters(q, relational_models.JobSeekerEducation)
    res = await session.exec(q)
    education_degree_distribution = [TopItem(key=str(row[0]), count=int(row[1])) for row in res.all()]

    return AdvancedStatsResponse(
        totals=totals,
        applications_by_status=applications_by_status,
        top_skills=top_skills,
        applications_per_posting=applications_per_posting,
        average_time_to_first_application_days=average_time_to_first_application_days,
        resumes_by_visibility=resumes_by_visibility,
        applicants_by_province=applicants_by_province,
        education_degree_distribution=education_degree_distribution,
    )