from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import UUID4
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

from app.config import Config
from app.elasticsearch.indexes.posts_index import posts_index
from app.elasticsearch.indexes.users_index import users_index
from app.elasticsearch.url import elastic
from app.email.bodies import EmailInfoAdmin
from app.email.send_email import send_email_info
from app.postgres.crud import get_users_by_role
from app.postgres.engine import get_db
from app.postgres.tables import User, Like, Post
from app.schemas import users, admin
from app.security.authz import get_current_admin
from app.security.password import hash_password


router = APIRouter()


# ================================================================
# Loguru settings
# ================================================================


def is_admin_record(record):
    return '[adm]' in record['message']


logger.add('app/logs/admin/adm.log',
           format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <cyan>{message}</cyan>",
           filter=is_admin_record,
           rotation=Config.rotation_size, retention=Config.retention_time_days, level="INFO")


# ================================================================
# Get all moderators/admins funcs
# ================================================================


@router.get('/moderators', response_model=list[admin.ReturnFullUserEmail])
async def get_all_moderators(offset: int = 0,
                             limit: int = 10,
                             current_admin: users.ReturnUser = Depends(get_current_admin)):

    moderators = await get_users_by_role(role='moderator', offset=offset, limit=limit)
    if not moderators:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail='Moderators not found'
        )
    return moderators


@router.get('/admins', response_model=list[admin.ReturnFullUserEmail])
async def get_all_admins(offset: int = 0,
                         limit: int = 10,
                         current_admin: users.ReturnUser = Depends(get_current_admin)):
    admins = await get_users_by_role(role='admin', offset=offset, limit=limit)
    if not admins:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail='Admins not found'
        )
    return admins


# ================================================================
# Get moderators/admins logs funcs
# ================================================================


@router.get('/moderator-logs')
async def get_moderators_logs(current_admin: users.ReturnUser = Depends(get_current_admin)):
    try:
        with open('app/logs/moderator/mdr.log', 'r') as file:
            logs = file.readlines()
            return logs
    except FileNotFoundError:
        return "Log file not found"


@router.get('/admin-logs')
async def get_admins_logs(current_admin: users.ReturnUser = Depends(get_current_admin)):
    try:
        with open('app/logs/admin/adm.log', 'r') as file:
            logs = file.readlines()
            return logs
    except FileNotFoundError:
        return "Log file not found"


# ================================================================
# Create user func for admin
# ================================================================


@router.post('/create-user')
async def create_user(user_data: admin.AdminCreateUser,
                      current_admin: users.ReturnUser = Depends(get_current_admin),
                      db: AsyncSession = Depends(get_db)):
    """ Admin can create a new user with any role """

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

    # Creating user in postgres
    user = User(username=user_data.username,
                email=user_data.email,
                hashed_password=hash_password(user_data.password),
                role=user_data.role)
    db.add(user)
    await db.commit()

    # Creating user in elasticsearch
    await elastic.index(index='users', document=users.ElasticUser(username=user.username).dict())

    # Writing a log to file
    logger.info(f'[adm] Admin [ {current_admin.UUID} ] created user [ user:{user.UUID} ][ role:{user.role} ]')

    return {'UUID': str(current_admin.UUID),
            'response': {
                'detail': 'User has been successfully created',
                'status': 200
            }}


# ================================================================
# Change users role func for admin
# ================================================================


@router.put('/{user_uuid}')
async def change_role(user_uuid: UUID4,
                      new_role: str,
                      db: AsyncSession = Depends(get_db),
                      current_admin: users.ReturnUser = Depends(get_current_admin)):
    """ Admin can change users role with role """

    user = await db.scalar(select(User).where(User.UUID == user_uuid))
    if not user:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail='User does not exist'
        )

    # Updating role in table User
    old_role = user.role
    user.role = new_role
    await db.commit()

    # Writing a log to file
    logger.info(f'[adm] Admin [ {current_admin.UUID} ] changed user role [ user:{user.UUID} ]: {old_role} -> {new_role}')

    return {'UUID': str(current_admin.UUID),
            'response': {
                'detail': 'Users role has been successfully changed',
                'status': 200
            }}


# ================================================================
# Delete user with any role func for admin
# ================================================================


@router.delete('/{user_uuid}/delete')
async def delete_any_user(user_uuid: UUID4,
                      db: AsyncSession = Depends(get_db),
                      current_admin: users.ReturnUser = Depends(get_current_admin)):
    """ Admin can delete user with any role """

    user = await db.scalar(select(User).where(User.UUID == user_uuid))

    if not user:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail='User does not exist'
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
    await send_email_info(mail=users.EmailSchema(email=[user.email]), body=EmailInfoAdmin.delete_user)

    # Writing a log to file
    logger.info(f'[adm] Admin [ {current_admin.UUID} ] deleted user [ user:{user.UUID} ][ role:{user.role} ]')

    return {'UUID': str(current_admin.UUID),
            'response': {
                'detail': 'User has been successfully deleted',
                'status': 200
            }}


# ================================================================
# Creating indexes in elasticsearch (required: master_key)
# ================================================================


@router.post('/indexes')
async def create_es_indexes(master_key: str):
    if master_key != Config.master_key:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail='Bad key'
        )

    await elastic.indices.create(index='posts', body=posts_index)
    await elastic.indices.create(index='users', body=users_index)

    return {'detail': 'Indexes has been successfully created', 'status': 200}
