from random import randint

from fastapi import APIRouter, Depends, HTTPException, Response
from redis.asyncio import StrictRedis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND, HTTP_401_UNAUTHORIZED

from app.config import Config
from app.elasticsearch.url import elastic
from app.email.bodies import EmailCode, EmailInfo
from app.email.send_email import send_email_code, send_email_info
from app.postgres.engine import get_db
from app.postgres.tables import User, Post, Like
from app.redis.crud import hsetex
from app.redis.engine import get_redis
from app.schemas import users
from app.security.JWT import create_mail_token
from app.security.authz import get_current_user, auth_email
from app.security.password import verify_password, hash_password

router = APIRouter()


# ================================================================
# Description for about me func
# ================================================================


@router.post("/update-about-me", response_model=users.ReturnFullUser, status_code=200)
async def update_about_me(about_me: users.AboutMe,
                          current_user: users.ReturnUser = Depends(get_current_user),
                          db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.UUID == current_user.UUID))

    if not user:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND,
                            detail="User not found")

    user.about_me = about_me.description
    await db.commit()

    return users.ReturnFullUser(UUID=current_user.UUID, username=current_user.username, about_me=user.about_me,
                                likes=user.likes, role=user.role)


# ================================================================
# Funcs:
# 1) DELETE account -> send email
# 2) Verify email -> deleting
# 3) Resend email -> send email
# ================================================================


@router.delete('/delete-account')
async def delete_account(response: Response,
                         db: AsyncSession = Depends(get_db),
                         redis: StrictRedis = Depends(get_redis),
                         current_user: users.ReturnUser = Depends(get_current_user)):

    user = await db.scalar(select(User).where(User.UUID == current_user.UUID))
    if not user:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail='Your account does not exist'
        )

    # Email
    email_code = randint(100000, 999999)
    await send_email_code(mail=users.EmailSchema(email=[user.email]),
                          email_code=email_code, body=EmailCode.code_for_delete)

    # Redis
    await hsetex(redis=redis,
                 name=str(user.UUID),
                 mapping={'email_code': email_code},
                 time=Config.mail_token_expire_seconds)

    # JWT
    mail_token = await create_mail_token(username=user.username)
    response.set_cookie(key='Mail', value=mail_token, httponly=True)

    return {'UUID': str(user.UUID),
            'response': {
                'detail': 'Email for delete account has been successfully sent',
                'status': 200
            }}


@router.post('/verify-delete-account')
async def verify_delete_account(input_email_code: int,
                                current_auth_email: users.Username = Depends(auth_email),
                                db: AsyncSession = Depends(get_db),
                                redis: StrictRedis = Depends(get_redis)):

    user = await db.scalar(select(User).where(User.username == current_auth_email.username))
    if not user:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail="User does not exist"
        )

    redis_email_code = await redis.hgetall(name=str(user.UUID))
    if not redis_email_code:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail="User data not found"
        )

    if input_email_code != int(redis_email_code['email_code']):
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid email code"
        )

    # Deleting likes user in postgres
    likes = await db.scalars(select(Like).where(Like.user_UUID == user.UUID))
    for like in likes:
        await db.delete(like)

    posts = await db.scalars(select(Post).where(Post.owner_UUID == user.UUID))
    for post in posts.all():
        # Deleting posts current user from postgres
        await db.delete(post)
        # Deleting posts current user from elasticsearch
        await elastic.delete_by_query(
            index='posts',
            body={
                "query": {
                    "match": {
                        "id": post.id
                    }
                }
            }
        )
    # Deleting current user from postgres
    await db.delete(user)
    await db.commit()
    # Deleting current user from elasticsearch
    await elastic.delete_by_query(
        index='users',
        body={
            "query": {
                "match": {
                    "username": user.username
                }
            }
        }
    )

    # Sending email with information about delete account to user mail
    await send_email_info(mail=users.EmailSchema(email=[user.email]), body=EmailInfo.delete_account_info)

    return {'UUID': str(user.UUID),
            'response': {
                'detail': 'Your account and all yours posts have been successfully deleted',
                'status': 200
            }}


@router.post('/resend-delete-account')
async def resend_delete_account(response: Response,
                                current_auth_email: users.Username = Depends(auth_email),
                                redis: StrictRedis = Depends(get_redis),
                                db: AsyncSession = Depends(get_db)):

    user = await db.scalar(select(User).where(User.username == current_auth_email.username))
    if not user:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail="User does not exist"
        )

    user_data = await redis.hgetall(name=str(user.UUID))

    if not user_data:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND,
                            detail="User data not found")

    # Email
    email_code = randint(100000, 999999)
    await send_email_code(mail=users.EmailSchema(email=[user.email]),
                          email_code=email_code, body=EmailCode.code_for_delete)

    # Redis
    await hsetex(redis=redis,
                 name=str(user.UUID),
                 mapping={'email_code': email_code},
                 time=Config.mail_token_expire_seconds)

    # JWT
    mail_token = await create_mail_token(username=user.username)
    response.set_cookie(key='Mail', value=mail_token, httponly=True)

    return {'UUID': str(user.UUID),
            'response': {
                'detail': 'Email for delete account has been successfully resent',
                'status': 200
            }}


# ================================================================
# Change USERNAME account func
# ================================================================


@router.put('/change-username')
async def change_username(form: users.ChangeUsername,
                          db: AsyncSession = Depends(get_db),
                          current_user: users.ReturnUser = Depends(get_current_user)):

    user = await db.scalar(select(User).where(User.UUID == current_user.UUID))
    if not user:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail='Your account does not exist'
        )

    existing_user = await db.scalar(select(User).where(User.username == form.new_username))
    if existing_user:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail='Username already taken'
        )

    if not verify_password(plain_password=form.password,
                           hashed_password=user.hashed_password):
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail='Wrong password'
        )

    # Updating username in table User
    user.username = form.new_username
    await db.commit()

    # Updating username in posts user in table Post
    await db.execute(
        update(Post)
        .where(Post.owner_UUID == current_user.UUID)
        .values(owner_username=form.new_username)
    )
    await db.commit()

    # Updating username in index users in elasticsearch
    await elastic.update_by_query(
        index='users',
        body={
            "script": {
                "source": "ctx._source.username = params.new_username",
                "params": {
                    "new_username": form.new_username
                }
            },
            "query": {
                "match": {
                    "username": current_user.username
                }
            }
        }
    )

    # Sending email with information about changed username to user mail
    await send_email_info(mail=users.EmailSchema(email=[user.email]), body=EmailInfo.change_username_info)

    return {'UUID': str(user.UUID),
            'response': {
                'detail': 'Username has been successfully changed',
                'status': 200
            }}


# ================================================================
# Funcs:
# 1) Change EMAIL account -> send email
# 2) Verify email -> changing email
# 3) Resend email -> send email
# ================================================================


@router.put('/change-email')
async def change_email(form: users.ChangeEmail,
                       response: Response,
                       db: AsyncSession = Depends(get_db),
                       redis: StrictRedis = Depends(get_redis),
                       current_user: users.ReturnUser = Depends(get_current_user)):
    existing_user = await db.scalar(select(User).where(User.email == form.new_email))
    if existing_user:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail='Account with this email already exist'
        )

    if form.new_email != form.repeat_new_email:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail='Wrong repeat email'
        )

    user = await db.scalar(select(User).where(User.username == current_user.username))
    if not verify_password(plain_password=form.password,
                           hashed_password=user.hashed_password):
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail='Wrong password'
        )

    # Email
    email_code = randint(100000, 999999)
    await send_email_code(mail=users.EmailSchema(email=[form.new_email]),
                          email_code=email_code, body=EmailCode.code_for_change_email)

    # Redis
    await hsetex(redis=redis,
                 name=str(user.UUID),
                 mapping={'email_code': email_code,
                          'new_email': form.new_email},
                 time=Config.mail_token_expire_seconds)

    # JWT
    mail_token = await create_mail_token(username=user.username)
    response.set_cookie(key='Mail', value=mail_token, httponly=True)

    return {'UUID': str(user.UUID),
            'response': {
                'detail': 'Email for change email address has been successfully sent',
                'status': 200
            }}


@router.post('/verify-change-email')
async def verify_change_email(input_email_code: int,
                              current_auth_email: users.Username = Depends(auth_email),
                              db: AsyncSession = Depends(get_db),
                              redis: StrictRedis = Depends(get_redis)):

    user = await db.scalar(select(User).where(User.username == current_auth_email.username))
    if not user:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail="User does not exist"
        )

    redis_email_code = await redis.hgetall(name=str(user.UUID))
    if not redis_email_code:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail="User data not found"
        )

    if input_email_code != int(redis_email_code['email_code']):
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid email code"
        )

    # Updating email address in table User
    user.email = redis_email_code['new_email']
    await db.commit()

    # Sending email with information about change email address to user mail
    await send_email_info(mail=users.EmailSchema(email=[user.email]), body=EmailInfo.change_email_info)

    return {'UUID': str(user.UUID),
            'response': {
                'detail': 'Your email address has been successfully changed',
                'status': 200
            }}


@router.post('/resend-change-email')
async def resend_change_email(response: Response,
                              current_auth_email: users.Username = Depends(auth_email),
                              redis: StrictRedis = Depends(get_redis),
                              db: AsyncSession = Depends(get_db)):

    user = await db.scalar(select(User).where(User.username == current_auth_email.username))
    if not user:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail="User does not exist"
        )

    user_data = await redis.hgetall(name=str(user.UUID))

    if not user_data:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND,
                            detail="User data not found")

    # Email
    email_code = randint(100000, 999999)
    await send_email_code(mail=users.EmailSchema(email=[user_data['new_email']]),
                          email_code=email_code, body=EmailCode.code_for_change_email)

    # Redis
    await hsetex(redis=redis,
                 name=str(user.UUID),
                 mapping={'email_code': email_code,
                          'new_email': user_data['new_email']},
                 time=Config.mail_token_expire_seconds)

    # JWT
    mail_token = await create_mail_token(username=user.username)
    response.set_cookie(key='Mail', value=mail_token, httponly=True)

    return {'UUID': str(user.UUID),
            'response': {
                'detail': 'Email for change email address has been successfully resent',
                'status': 200
            }}


# ================================================================
# Funcs:
# 1) Change PASSWORD account -> send email
# 2) Verify email -> changing password
# 3) Resend email -> send email
# ================================================================


@router.put('/change-password')
async def change_password(form: users.ChangePassword,
                          response: Response,
                          db: AsyncSession = Depends(get_db),
                          redis: StrictRedis = Depends(get_redis),
                          current_user: users.ReturnUser = Depends(get_current_user)):
    user = await db.scalar(select(User).where(User.UUID == current_user.UUID))
    if not user:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail="User does not exist"
        )

    if form.password != form.repeat_password:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail='Wrong repeat password'
        )

    # Email
    email_code = randint(100000, 999999)
    await send_email_code(mail=users.EmailSchema(email=[user.email]),
                          email_code=email_code, body=EmailCode.code_for_change_password)

    # Redis
    await hsetex(redis=redis,
                 name=str(user.UUID),
                 mapping={'email_code': email_code,
                          'new_password': form.password},
                 time=Config.mail_token_expire_seconds)

    # JWT
    mail_token = await create_mail_token(username=user.username)
    response.set_cookie(key='Mail', value=mail_token, httponly=True)

    return {'UUID': str(user.UUID),
            'response': {
                'detail': 'Email for change password has been successfully sent',
                'status': 200
            }}


@router.post('/verify-change-password')
async def verify_change_password(input_email_code: int,
                                 current_auth_email: users.Username = Depends(auth_email),
                                 db: AsyncSession = Depends(get_db),
                                 redis: StrictRedis = Depends(get_redis)):

    user = await db.scalar(select(User).where(User.username == current_auth_email.username))
    if not user:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail="User does not exist"
        )

    redis_email_code = await redis.hgetall(name=str(user.UUID))
    if not redis_email_code:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail="User data not found"
        )

    if input_email_code != int(redis_email_code['email_code']):
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid email code"
        )

    # Updating password in table User
    user.hashed_password = hash_password(redis_email_code['new_password'])
    await db.commit()

    # Sending email with information about change password to user mail
    await send_email_info(mail=users.EmailSchema(email=[user.email]), body=EmailInfo.change_password_info)

    return {'UUID': str(user.UUID),
            'response': {
                'detail': 'Your password has been successfully changed',
                'status': 200
            }}


@router.post('/resend-change-password')
async def resend_change_password(response: Response,
                                 current_auth_email: users.Username = Depends(auth_email),
                                 redis: StrictRedis = Depends(get_redis),
                                 db: AsyncSession = Depends(get_db)):

    user = await db.scalar(select(User).where(User.username == current_auth_email.username))
    if not user:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail="User does not exist"
        )

    user_data = await redis.hgetall(name=str(user.UUID))

    if not user_data:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND,
                            detail="User data not found")

    # Email
    email_code = randint(100000, 999999)
    await send_email_code(mail=users.EmailSchema(email=[user.email]),
                          email_code=email_code, body=EmailCode.code_for_change_password)

    # Redis
    await hsetex(redis=redis,
                 name=str(user.UUID),
                 mapping={'email_code': email_code,
                          'new_password': user_data['new_password']},
                 time=Config.mail_token_expire_seconds)

    # JWT
    mail_token = await create_mail_token(username=user.username)
    response.set_cookie(key='Mail', value=mail_token, httponly=True)

    return {'UUID': str(user.UUID),
            'response': {
                'detail': 'Email for change password has been successfully resent',
                'status': 200
            }}
