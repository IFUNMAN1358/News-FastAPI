from sqlalchemy import select, or_, desc
from pydantic import UUID4

from app.postgres.engine import async_session
from app.postgres.tables import User, Post


async def get_user_by_email_or_username(email_or_username: str):
    db = async_session()
    try:
        user = await db.scalar(select(User).where(or_(User.username == email_or_username,
                                                      User.email == email_or_username)))
        return user
    finally:
        await db.close()


async def get_user_by_id(user_id: UUID4):
    db = async_session()
    try:
        user = await db.scalar(select(User).where(User.UUID == user_id))
        return user
    finally:
        await db.close()


async def get_posts_without_search_query(offset: int,
                                         limit: int):
    db = async_session()
    try:
        result = await db.execute(
            select(Post)
            .order_by(desc(Post.likes), desc(Post.created_at))
            .offset(offset * 10)
            .limit(limit)
        )
        return result
    finally:
        await db.close()


async def get_posts_user(user_id: UUID4,
                         offset: int,
                         limit: int):
    db = async_session()
    try:
        result = await db.execute(
            select(Post)
            .where(Post.owner_UUID == user_id)
            .order_by(desc(Post.likes), desc(Post.created_at))
            .offset(offset * 10)
            .limit(limit)
        )
        return result
    finally:
        await db.close()


async def get_posts_by_ids(ids: list,
                           offset: int,
                           limit: int):
    db = async_session()
    try:
        result = await db.execute(
            select(Post)
            .where(Post.id.in_(ids))
            .order_by(desc(Post.likes), desc(Post.created_at))
            .offset(offset)
            .limit(limit)
        )
        return result
    finally:
        await db.close()


async def get_posts_by_user_id(user_UUID: UUID4):
    db = async_session()
    try:
        result = await db.scalars(select(Post).where(Post.owner_UUID == user_UUID))
        return result.all()
    finally:
        await db.close()


async def get_posts_by_username(username: str,
                                offset: int,
                                limit: int):
    db = async_session()
    try:
        result = await db.execute(
            select(Post)
            .where(Post.owner_username == username)
            .order_by(desc(Post.likes))
            .offset(offset)
            .limit(limit)
        )
        return result
    finally:
        await db.close()


async def get_users_by_usernames(usernames: list,
                                 offset: int,
                                 limit: int):
    db = async_session()
    try:
        result = await db.execute(
            select(User)
            .where(User.username.in_(usernames))
            .order_by(desc(User.likes))
            .offset(offset)
            .limit(limit)
        )
        return result
    finally:
        await db.close()


async def get_users_without_search_query(offset: int,
                                         limit: int):
    db = async_session()
    try:
        result = await db.execute(
            select(User)
            .order_by(desc(User.likes))
            .offset(offset * 10)
            .limit(limit)
        )
        return result
    finally:
        await db.close()


async def get_users_by_role(role: str,
                            offset: int,
                            limit: int):
    db = async_session()
    try:
        result = await db.execute(
            select(User)
            .where(User.role == role)
            .offset(offset * 10)
            .limit(limit)
        )
        return result.scalars().all()
    finally:
        await db.close()
