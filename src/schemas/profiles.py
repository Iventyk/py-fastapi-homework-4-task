from datetime import date
from fastapi import UploadFile
from pydantic import BaseModel, field_validator, ConfigDict

from database.models.accounts import GenderEnum
from validation.profile import validate_name, validate_image, validate_gender, validate_birth_date


class UserProfileCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: UploadFile | None = None

    @field_validator("first_name")
    @classmethod
    def check_first_name(cls, value: str) -> str:
        validate_name(value)
        return value

    @field_validator("last_name")
    @classmethod
    def check_last_name(cls, value: str) -> str:
        validate_name(value)
        return value

    @field_validator("gender")
    @classmethod
    def check_gender(cls, value: str) -> str:
        validate_gender(value)
        return value

    @field_validator("date_of_birth")
    @classmethod
    def check_birth_date(cls, value: date) -> date:
        validate_birth_date(value)
        return value

    @field_validator("info")
    @classmethod
    def check_info(cls, value: str) -> str:
        if not value or value.strip() == "":
            raise ValueError("Info cannot be empty or just whitespace")
        return value

    @field_validator("avatar")
    @classmethod
    def check_avatar(cls, value: UploadFile | None) -> UploadFile | None:
        if value:
            validate_image(value)
        return value


class UserProfileResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str | None = None
    last_name: str | None = None
    gender: GenderEnum | None = None
    date_of_birth: date | None = None
    info: str | None = None
    avatar: str | None = None
