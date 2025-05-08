from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query

from dependencies import get_session
from sqlalchemy.ext.asyncio import AsyncSession

from models.relational_models import JobSeekerPersonalInformation, User
from schemas.job_seeker_personal_information import JobSeekerPersonalInformationCreate, JobSeekerPersonalInformationUpdate
from schemas.relational_schemas import RelationalJobSeekerPersonalInformationPublic
from sqlmodel import and_, not_, or_, select

from utilities.authentication import get_password_hash
from utilities.enumerables import IranProvinces, JobSeekerGender, JobSeekerMaritalStatus, JobSeekerMilitaryServiceStatus, LogicalOperator


router = APIRouter()


@router.get(
    "/job_seeker_personal_informations/",
    response_model=list[RelationalJobSeekerPersonalInformationPublic],
)
async def get_job_seeker_personal_informations (
    *,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
):
    jspis_query = select(JobSeekerPersonalInformation).offset(offset).limit(limit).order_by(JobSeekerPersonalInformation.created_at)
    jspis = await session.exec(jspis_query)

    return jspis.all()


@router.post(
    "/job_seeker_personal_informations/",
    response_model=RelationalJobSeekerPersonalInformationPublic,
)
async def create_job_seeker_personal_information(
        *,
        session: AsyncSession = Depends(get_session),
        job_seeker_personal_information_create: JobSeekerPersonalInformationCreate,
):
    try:
        db_jspi = JobSeekerPersonalInformation(
            residence_province=job_seeker_personal_information_create.residence_province,
            residence_address=job_seeker_personal_information_create.residence_address,
            marital_status=job_seeker_personal_information_create.marital_status,
            birth_year=job_seeker_personal_information_create.birth_year,
            gender=job_seeker_personal_information_create.gender,
            military_service_status=job_seeker_personal_information_create.military_service_status,
            job_seeker_resume_id=job_seeker_personal_information_create.job_seeker_resume_id
        )

        session.add(db_jspi)
        await session.commit()
        await session.refresh(db_jspi)

        return RelationalJobSeekerPersonalInformationPublic.model_validate(db_jspi)

    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"{e}خطا در ایجاد اطلاعات کارجو: "
        )


@router.get(
    "/job_seeker_personal_informations/{job_seeker_personal_information_id}",
    response_model=RelationalJobSeekerPersonalInformationPublic,
)
async def get_job_seeker_personal_information(
        *,
        session: AsyncSession = Depends(get_session),
        job_seeker_personal_information_id: UUID,
):
    jspi = await session.get(JobSeekerPersonalInformation, job_seeker_personal_information_id)
    if not jspi:
        raise HTTPException(status_code=404, detail="اطلاعات کارجو پیدا نشد")

    return jspi


@router.patch(
    "/job_seeker_personal_informations/{job_seeker_personal_information_id}",
    response_model=RelationalJobSeekerPersonalInformationPublic,
)
async def patch_job_seeker_personal_information(
        *,
        session: AsyncSession = Depends(get_session),
        job_seeker_personal_information_id: UUID,
        job_seeker_personal_information_update: JobSeekerPersonalInformationUpdate,
):
    jspi = await session.get(JobSeekerPersonalInformation, job_seeker_personal_information_id)
    if not jspi:
        raise HTTPException(status_code=404, detail="اطلاعات کارجو پیدا نشد")

    update_data = job_seeker_personal_information_update.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["password"] = get_password_hash(update_data["password"])

    jspi.sqlmodel_update(update_data)

    await session.commit()
    await session.refresh(jspi)

    return jspi


@router.delete(
    "/job_seeker_personal_informations/{job_seeker_personal_information_id}",
    response_model=dict[str, str],
)
async def delete_user(
    *,
    session: AsyncSession = Depends(get_session),
    job_seeker_personal_information_id: UUID,
):
    jspi = await session.get(JobSeekerPersonalInformation, job_seeker_personal_information_id)
    if not jspi:
        raise HTTPException(status_code=404, detail="اطلاعات کارجو پیدا نشد")

    await session.delete(jspi)
    await session.commit()

    return {"msg": "اطلاعات کارجو با موفقیت حذف شد"}


@router.get(
    "/job_seeker_personal_informations/search/",
    response_model=list[RelationalJobSeekerPersonalInformationPublic],
)
async def search_admins(
        *,
        session: AsyncSession = Depends(get_session),
        eresidence_province: IranProvinces | None = None,
        residence_address: str | None = None,
        marital_status: JobSeekerMaritalStatus | None = None,
        birth_year: int | None = None,
        gender: JobSeekerGender | None = None,
        military_service_status: JobSeekerMilitaryServiceStatus | None = None,
        operator: LogicalOperator,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, le=100),
):
    conditions = []
    if eresidence_province:
        conditions.append(JobSeekerPersonalInformation.eresidence_province == eresidence_province)
    if residence_address:
        conditions.append(JobSeekerPersonalInformation.residence_address.ilike(f"%{residence_address}%"))
    if marital_status:
        conditions.append(JobSeekerPersonalInformation.marital_status == marital_status)
    if birth_year:
        conditions.append(JobSeekerPersonalInformation.birth_year == birth_year)
    if gender:
        conditions.append(JobSeekerPersonalInformation.gender == gender)
    if military_service_status:
        conditions.append(JobSeekerPersonalInformation.military_service_status == military_service_status)

    if not conditions:
        raise HTTPException(status_code=400, detail="هیچ مقداری برای جست و جو وجود ندارد")

    if operator == LogicalOperator.AND:
        query = select(JobSeekerPersonalInformation).where(and_(*conditions))
    elif operator == LogicalOperator.OR:
        query = select(JobSeekerPersonalInformation).where(or_(*conditions))
    elif operator == LogicalOperator.NOT:
        query = select(JobSeekerPersonalInformation).where(not_(and_(*conditions)))
    else:
        raise HTTPException(status_code=400, detail="عملگر نامعتبر مشخص شده است")

    result = await session.exec(query.offset(offset).limit(limit))
    jspis = result.all()
    if not jspis:
        raise HTTPException(status_code=404, detail="اطلاعات کارجو پیدا نشد")

    return jspis
