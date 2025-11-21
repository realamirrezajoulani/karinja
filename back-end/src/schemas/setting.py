from uuid import UUID
from datetime import datetime
from sqlmodel import Field, SQLModel

from schemas.base.setting import SettingBase
from utilities.enumerables import SettingType


class SettingPublic(SettingBase):
    id: UUID
    created_at: datetime
    updated_at: datetime | None


class SettingCreate(SettingBase):
    user_id: UUID


class SettingUpdate(SQLModel):
    key: str | None = Field(default=None, unique=True, max_length=128, index=True)
    value: str | None = Field(default=None)
    value_type: SettingType | None = Field(default=None, index=True)
    description: str | None = Field(default=None, max_length=512)
    is_sensitive: bool | None = Field(default=None)
    is_active: bool | None = Field(default=None)
