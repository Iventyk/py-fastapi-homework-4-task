from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from database import get_db, UserModel, UserProfileModel
from database.models.accounts import GenderEnum
from schemas.profiles import UserProfileResponseSchema
from storages.s3 import S3StorageClient
from config import get_s3_storage_client
from fastapi.security import OAuth2PasswordBearer


router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/accounts/login/")


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> UserModel:

    user_id = int(token)
    stmt = select(UserModel).where(UserModel.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.post(
    "/",
    response_model=UserProfileResponseSchema,
    summary="Create or Update User Profile",
)
async def create_or_update_profile(
        first_name: str = Form(),
        last_name: str = Form(),
        gender: str = Form(),
        date_of_birth: str = Form(),
        info: str = Form(None),
        avatar: UploadFile | None = None,
        db: AsyncSession = Depends(get_db),
        current_user: UserModel = Depends(get_current_user),
        s3_client: S3StorageClient = Depends(get_s3_storage_client)
) -> UserProfileResponseSchema:

    from schemas.profiles import UserProfileCreateSchema
    from datetime import datetime

    profile_data = UserProfileCreateSchema(
        first_name=first_name,
        last_name=last_name,
        gender=gender,
        date_of_birth=datetime.strptime(date_of_birth, "%Y-%m-%d").date(),
        info=info,
        avatar=avatar
    )

    profile = current_user.profile
    if not profile:
        profile = UserProfileModel(user_id=current_user.id)

    profile.first_name = profile_data.first_name
    profile.last_name = profile_data.last_name
    profile.gender = GenderEnum(profile_data.gender) if profile_data.gender else None
    profile.date_of_birth = profile_data.date_of_birth
    profile.info = profile_data.info

    if profile_data.avatar:
        avatar_file = profile_data.avatar
        file_name = f"avatars/user_{current_user.id}_{avatar_file.filename}"
        file_bytes = await avatar_file.read()
        await s3_client.upload_file(file_name, file_bytes)
        profile.avatar = await s3_client.get_file_url(file_name)

    try:
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save profile") from e

    return UserProfileResponseSchema.model_validate(profile)
