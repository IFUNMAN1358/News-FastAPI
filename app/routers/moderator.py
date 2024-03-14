from fastapi import APIRouter, Depends, HTTPException
from pydantic import UUID4
from sqlalchemy import select, and_, update, or_
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND, HTTP_403_FORBIDDEN
from loguru import logger

from app.config import Config
from app.elasticsearch.url import elastic
from app.email.bodies import EmailInfoModerator
from app.email.send_email import send_email_info
from app.postgres.engine import get_db
from app.postgres.tables import User, Post, Like
from app.schemas import users, posts
from app.security.authz import get_current_moderator


router = APIRouter()


# ================================================================
# Loguru settings
# ================================================================


def is_moderator_record(record):
    return '[mdr]' in record['message']


logger.add('app/logs/moderator/mdr.log',
           format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <cyan>{message}</cyan>",
           filter=is_moderator_record,
           rotation=Config.rotation_size, retention=Config.retention_time_days, level="INFO")


# ================================================================
# Rename user func for moderator
# ================================================================


@router.put('/{user_uuid}/rename')
async def rename_user(user_uuid: UUID4,
                      new_username: str,
                      db: AsyncSession = Depends(get_db),
                      current_moderator: users.ReturnUser = Depends(get_current_moderator)):
    """ Moderator can change users username (except 'admin' role) """

    user = await db.scalar(select(User).where(and_(User.UUID == user_uuid,
                                                   or_(User.role == 'user', User.role == 'moderator'))))

    if not user:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail='User does not exist'
        )

    if user.role == 'admin':
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail='You dont have permission to access'
        )

    existing_user = await db.scalar(select(User).where(User.username == new_username))

    if existing_user:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail='Username already taken'
        )

    # Updating username in table User
    old_username = user.username
    user.username = new_username
    await db.commit()

    # Updating username in posts user in table Post
    await db.execute(
        update(Post)
        .where(Post.owner_UUID == user.UUID)
        .values(owner_username=new_username)
    )
    await db.commit()

    # Updating username in index users in elasticsearch
    await elastic.update_by_query(
        index='users',
        body={
            "script": {
                "source": "ctx._source.username = params.new_username",
                "params": {
                    "new_username": new_username
                }
            },
            "query": {
                "match": {
                    "username": user.username
                }
            }
        }
    )

    # Sending email with information about changed username to user mail
    await send_email_info(mail=users.EmailSchema(email=[user.email]), body=EmailInfoModerator.rename_user)

    # Writing a log to file
    logger.info(f'[mdr] Moderator [ {current_moderator.UUID} ] renamed user [ {user.UUID} ]:'
                f' {old_username} -> {new_username}')

    return {'UUID': str(current_moderator.UUID),
            'response': {
                'detail': 'Users username has been successfully changed',
                'status': 200
            }}


# ================================================================
# Delete user func for moderator
# ================================================================


@router.delete('/{user_uuid}/delete')
async def delete_user(user_uuid: UUID4,
                      db: AsyncSession = Depends(get_db),
                      current_moderator: users.ReturnUser = Depends(get_current_moderator)):
    """ Moderator can delete user with role "user" """

    user = await db.scalar(select(User).where(and_(User.UUID == user_uuid,
                                                   User.role == 'user')))
    if not user:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail='User does not exist'
        )

    if not user.role == 'user':
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail='User has a role above "user"'
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
    await send_email_info(mail=users.EmailSchema(email=[user.email]), body=EmailInfoModerator.delete_user)

    # Writing a log to file
    logger.info(f'[mdr] Moderator [ {current_moderator.UUID} ] deleted user [ {user.UUID} ]')

    return {'UUID': str(current_moderator.UUID),
            'response': {
                'detail': 'User has been successfully deleted',
                'status': 200
            }}


# ================================================================
# Update users post func for moderator
# ================================================================


@router.put('/posts/{post_id}')
async def update_post(post_id: int,
                      input_post: posts.CreatePost,
                      db: AsyncSession = Depends(get_db),
                      current_moderator: users.ReturnUser = Depends(get_current_moderator)):
    """ Moderator can update users post """

    # Updating post in postgres
    post = await db.scalar(select(Post).where(Post.id == post_id))
    if post is None:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail='Post not found'
        )

    await db.execute(
        update(Post)
        .where(Post.id == post_id)
        .values(title=input_post.title, content=input_post.content)
    )
    await db.commit()

    # Updating post in elasticsearch
    await elastic.update_by_query(
        index='posts',
        body={
            "script": {
                "source": "ctx._source.title = params.title",
                "params": {
                    "title": input_post.title
                }
            },
            "query": {
                "match": {
                    "id": post_id
                }
            }
        }
    )

    user = await db.scalar(select(User).where(User.UUID == post.owner_UUID))

    # Sending email with information about updating users post to mail
    await send_email_info(mail=users.EmailSchema(email=[user.email]), body=EmailInfoModerator.change_post)

    # Writing a log to file
    logger.info(f'[mdr] Moderator [ {current_moderator.UUID} ] updated users post'
                f' [ user:{user.UUID} ][ post:{post.id} ]')

    return {'UUID': str(current_moderator.UUID),
            'response': {
                'detail': 'Users post has been successfully changed',
                'status': 200
            },
            'post': posts.ReturnFullPost(id=post.id, owner_UUID=post.owner_UUID, owner_username=post.owner_username,
                                         title=post.title, content=post.content,
                                         created_at=post.created_at, likes=post.likes)
            }


# ================================================================
# Delete users post func for moderator
# ================================================================


@router.delete('/posts/{post_id}')
async def delete_post(post_id: int,
                      db: AsyncSession = Depends(get_db),
                      current_moderator: users.ReturnUser = Depends(get_current_moderator)):
    """ Moderator can delete users post """

    # Deleting post in postgres
    post = await db.scalar(select(Post).where(Post.id == post_id))
    if post is None:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail='Post not found'
        )

    user = await db.scalar(select(User).where(User.UUID == post.owner_UUID))

    # Deleting likes post in postgres
    likes = await db.scalars(select(Like).where(Like.post_id == post.id))
    for like in likes:
        await db.delete(like)

    await db.delete(post)
    await db.commit()

    # Deleting post in elasticsearch
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

    # Sending email with information about delete users post to mail
    await send_email_info(mail=users.EmailSchema(email=[user.email]), body=EmailInfoModerator.delete_post)

    # Writing a log to file
    logger.info(f'[mdr] Moderator [ {current_moderator.UUID} ] deleted users post'
                f' [ user:{user.UUID} ][ post:{post.id} ]')

    return {'UUID': str(current_moderator.UUID),
            'response': {
                'detail': 'Users post has been successfully deleted',
                'status': 200
            }}
