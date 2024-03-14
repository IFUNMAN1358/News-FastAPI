from random import randint

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm
from redis.asyncio import StrictRedis
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED, HTTP_404_NOT_FOUND

from app.config import Config
from app.elasticsearch.url import elastic
from app.email.send_email import send_email_code, send_email_info
from app.postgres.crud import get_user_by_email_or_username
from app.postgres.engine import get_db
from app.postgres.tables import User
from app.redis.crud import hsetex
from app.redis.engine import get_redis
from app.schemas import users
from app.security.JWT import create_access_token, create_refresh_token, create_mail_token
from app.security.password import hash_password, verify_password
from app.security.authz import get_current_user, auth_email
from app.email.bodies import EmailCode, EmailInfo

router = APIRouter()


# ================================================================
# Registration func
# ================================================================


@router.post('/registration')
async def registration(response: Response,
                       user_data: users.RegisterUser,
                       db: AsyncSession = Depends(get_db),
                       redis: StrictRedis = Depends(get_redis)):

    if await db.scalar(select(User).where(or_(User.username == user_data.username,
                                              User.email == user_data.email))):
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail='User with this username or email already exist!'
        )

    if user_data.password != user_data.repeat_password:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail='Repeat password does not match password'
        )

    # Email
    email_code = randint(100000, 999999)
    await send_email_code(mail=users.EmailSchema(email=[user_data.email]),
                          email_code=email_code, body=EmailCode.code_for_registration)

    # Redis
    await hsetex(redis=redis,
                 name=user_data.username,
                 mapping={'username': user_data.username,
                          'email': user_data.email,
                          'password': user_data.password,
                          'email_code': email_code},
                 time=Config.mail_token_expire_seconds)

    # JWT
    mail_token = await create_mail_token(username=user_data.username)
    response.set_cookie(key='Mail', value=mail_token, httponly=True)

    return {'username': str(user_data.username),
            'response': {
                'detail': 'Email has been successfully sent',
                'status': 200
            }}


# ================================================================
# Verify_email_code and resend_email_code [registration] funcs
# ================================================================


@router.post('/verify-registration', response_model=users.ReturnUser, status_code=201)
async def verify_registration(input_email_code: int,
                              current_auth_email: users.Username = Depends(auth_email),
                              db: AsyncSession = Depends(get_db),
                              redis: StrictRedis = Depends(get_redis)):

    username = current_auth_email.username

    if await db.scalar(select(User).where(User.username == username)):
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail='User with this username or email already exist!'
        )

    data_username = await redis.hgetall(name=username)
    if not data_username:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail="User data not found"
        )

    if input_email_code != int(data_username['email_code']):
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid email code"
        )

    # Creating user in postgres
    user = User(username=data_username['username'],
                email=data_username['email'],
                hashed_password=hash_password(data_username['password']))
    db.add(user)
    await db.commit()

    # Creating user in elasticsearch
    await elastic.index(index='users', document=users.ElasticUser(username=user.username).dict())

    # Sending email with information about registration account to user mail
    await send_email_info(mail=users.EmailSchema(email=[user.email]), body=EmailInfo.registration_account_info)

    return users.ReturnUser(UUID=user.UUID,
                            username=user.username)


@router.post('/resend-registration')
async def resend_registration(response: Response,
                              current_auth_email: users.Username = Depends(auth_email),
                              redis: StrictRedis = Depends(get_redis)):

    username = current_auth_email.username
    user_data = await redis.hgetall(name=username)

    if not user_data:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND,
                            detail="User data not found")

    # Email
    email_code = randint(100000, 999999)
    await send_email_code(mail=users.EmailSchema(email=[user_data['email']]),
                          email_code=email_code, body=EmailCode.code_for_registration)

    # Redis
    await hsetex(redis=redis,
                 name=user_data['username'],
                 mapping={'username': user_data['username'],
                          'email': user_data['email'],
                          'password': user_data['password'],
                          'email_code': email_code},
                 time=Config.mail_token_expire_seconds)

    # JWT
    mail_token = await create_mail_token(username=user_data['username'])
    response.set_cookie(key='Mail', value=mail_token, httponly=True)

    return {'username': str(user_data['username']),
            'response': {
                'detail': 'Email has been successfully resent',
                'status': 200
            }}


# ================================================================
# Login and logout funcs
# ================================================================


@router.post("/login", response_model=users.ReturnUser, status_code=200)
async def login(response: Response,
                form_data: OAuth2PasswordRequestForm = Depends()):

    user = await get_user_by_email_or_username(form_data.username)

    if user is None:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail='User with this email or username not exist!'
        )

    if not verify_password(plain_password=form_data.password,
                           hashed_password=user.hashed_password):
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail='Wrong password!'
        )

    access_token = await create_access_token(user_uuid=user.UUID)
    refresh_token = await create_refresh_token(user_uuid=user.UUID)

    response.set_cookie(key='Access', value=access_token, httponly=True)
    response.set_cookie(key='Refresh', value=refresh_token, httponly=True)

    return users.ReturnUser(UUID=user.UUID,
                            username=user.username)


@router.post('/logout', response_model=users.ReturnUser, status_code=200)
async def logout(response: Response,
                 current_user: users.ReturnUser = Depends(get_current_user)):

    response.delete_cookie(key='Access')
    response.delete_cookie(key='Refresh')

    return users.ReturnUser(UUID=current_user.UUID,
                            username=current_user.username)
