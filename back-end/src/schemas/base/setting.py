from sqlmodel import Field, SQLModel

from utilities.enumerables import SettingType


class SettingBase(SQLModel):
    key: str = Field(..., max_length=128, index=True)
    value: str | None = Field(default=None)
    value_type: SettingType = Field(default=SettingType.STRING, index=True)
    description: str | None = Field(default=None, max_length=512)
    is_sensitive: bool = Field(default=False)
    is_active: bool = Field(default=True)
