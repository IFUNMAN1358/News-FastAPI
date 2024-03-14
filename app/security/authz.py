from fastapi import Request, HTTPException, Depends, Response
from jose import jwt, JWTError
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from app.config import Config
from app.postgres.crud import get_user_by_id
from app.postgres.engine import get_db
from app.postgres.tables import User
from app.schemas import users
from app.security.JWT import create_access_token


# ================================================================
# Mail authorization function
# ================================================================


async def auth_email(request: Request):
    credentials_exception = HTTPException(
        status_code=HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )

    mail_token = request.cookies.get('Mail')
    if mail_token is None:
        raise credentials_exception

    try:
        payload = jwt.decode(mail_token, Config.jwt_secret, algorithms=[Config.jwt_algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    return users.Username(username=username)


# ================================================================
# General authorization function
# ================================================================


async def get_current_user(request: Request,
                           response: Response):
    credentials_exception = HTTPException(
        status_code=HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )

    access_token = request.cookies.get('Access')
    if access_token is None:
        raise credentials_exception

    try:
        payload = jwt.decode(access_token, Config.jwt_secret, algorithms=[Config.jwt_algorithm])
        user_uuid: str = payload.get("sub")
        if user_uuid is None:
            raise credentials_exception
    except JWTError:
        refresh_token = request.cookies.get('Refresh')
        if refresh_token is None:
            raise credentials_exception

        try:
            payload = jwt.decode(refresh_token, Config.jwt_secret, algorithms=[Config.jwt_algorithm])
            user_uuid: str = payload.get("sub")
            if user_uuid is None:
                raise credentials_exception
        except JWTError:
            raise credentials_exception

        user = await get_user_by_id(user_id=user_uuid)
        if user is None:
            raise credentials_exception

        access_token = await create_access_token(user_uuid=user.UUID)
        response.set_cookie(key='Access', value=access_token, httponly=True)
        return users.ReturnUser(UUID=user.UUID, username=user.username)

    user = await get_user_by_id(user_id=user_uuid)
    if user is None:
        raise credentials_exception

    return users.ReturnUser(UUID=user.UUID, username=user.username)


# ================================================================
# Authorization function for moderator role
# ================================================================


async def get_current_moderator(db: AsyncSession = Depends(get_db),
                                current_user: users.ReturnUser = Depends(get_current_user)):
    moderator = await db.scalar(select(User).where(and_(User.UUID == current_user.UUID,
                                                        or_(User.role == 'moderator', User.role == 'admin'))))
    if not moderator:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail='You dont have permission to access'
        )
    return users.ReturnUser(UUID=moderator.UUID,
                            username=moderator.username)


# ================================================================
# Authorization function for admin role
# ================================================================


async def get_current_admin(db: AsyncSession = Depends(get_db),
                            current_moderator: users.ReturnUser = Depends(get_current_moderator)):
    admin = await db.scalar(select(User).where(and_(User.UUID == current_moderator.UUID,
                                                    User.role == 'admin')))
    if not admin:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail='You dont have permission to access'
        )
    return users.ReturnUser(UUID=admin.UUID,
                            username=admin.username)
