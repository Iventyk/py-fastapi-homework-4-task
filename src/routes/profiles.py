from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from database import get_db, UserModel, UserProfileModel
from database.models.accounts import GenderEnum
from schemas.profiles import UserProfileCreateSchema, UserProfileResponseSchema
from storages.s3 import S3StorageClient
from config import get_s3_storage_client, get_jwt_auth_manager
from fastapi.security import OAuth2PasswordBearer
from security.interfaces import JWTAuthManagerInterface


router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/accounts/login/")


async def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager)
) -> UserModel:
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    stmt = select(UserModel).where(UserModel.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or not active")
    return user


@router.post(
    "/users/{user_id}/profile/",
    response_model=UserProfileResponseSchema,
    summary="Create User Profile",
    status_code=status.HTTP_201_CREATED
)
async def create_profile(
        user_id: int,
        first_name: str = Form(),
        last_name: str = Form(),
        gender: str = Form(),
        date_of_birth: str = Form(),
        info: str = Form(),
        avatar: UploadFile | None = None,
        db: AsyncSession = Depends(get_db),
        current_user: UserModel = Depends(get_current_user),
        s3_client: S3StorageClient = Depends(get_s3_storage_client)
) -> UserProfileResponseSchema:
    if user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="You don't have permission to edit this profile.")

    if current_user.profile:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has a profile.")

    profile_data = UserProfileCreateSchema(
        first_name=first_name,
        last_name=last_name,
        gender=gender,
        date_of_birth=datetime.strptime(date_of_birth, "%Y-%m-%d").date(),
        info=info,
        avatar=avatar
    )

    profile = UserProfileModel(user_id=current_user.id)
    profile.first_name = profile_data.first_name
    profile.last_name = profile_data.last_name
    profile.gender = GenderEnum(profile_data.gender) if profile_data.gender else None
    profile.date_of_birth = profile_data.date_of_birth
    profile.info = profile_data.info

    if profile_data.avatar:
        try:
            avatar_file = profile_data.avatar
            file_name = f"avatars/user_{current_user.id}_{avatar_file.filename}"
            file_bytes = await avatar_file.read()
            await s3_client.upload_file(file_name, file_bytes)
            profile.avatar = await s3_client.get_file_url(file_name)
        except Exception:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Failed to upload avatar. Please try again later.")

    try:
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save profile") from e

    return UserProfileResponseSchema.model_validate(profile)
