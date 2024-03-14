from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_404_NOT_FOUND

from app.elasticsearch.url import elastic
from app.postgres.crud import get_users_by_usernames, get_users_without_search_query, get_posts_by_username
from app.postgres.engine import get_db
from app.postgres.tables import User
from app.schemas import users
from app.schemas import posts


router = APIRouter()


# ================================================================
# Full-text search with elasticsearch and postgres = list[user]
# ================================================================


@router.get('/', response_model=list[users.ReturnUserSearch], status_code=200)
async def get_users_with_search(query: str = None,
                                offset: int = 0,
                                limit: int = 10):
    """ Get a list of users (WITHOUT CONTENT) from db with search query / without search query """
    # If user has entered a search query
    if query:
        response = await elastic.search(index='users', body={
            "query": {
                "match": {
                    "username": {
                        "query": query,
                        "analyzer": "custom_analyzer",
                    }
                }
            }
        })
        usernames = [user['_source']['username'] for user in response['hits']['hits']]
        users_from_db = await get_users_by_usernames(usernames=usernames, offset=offset * 10, limit=limit)

    # Else, if user has not entered a search query
    else:
        users_from_db = await get_users_without_search_query(offset=offset * 10, limit=limit)

    # Checking existence for users
    result = users_from_db.scalars().all()
    if not result:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail='Users not found'
        )
    return result


# ================================================================
# Open profile user = user
# ================================================================


@router.get('/{username}', response_model=users.ReturnFullUser, status_code=200)
async def open_profile_user(username: str,
                            db: AsyncSession = Depends(get_db)):
    """ Return user profile (WITH CONTENT) from postgres """
    user = await db.scalar(select(User).where(User.username == username))
    if not user:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail='User not found'
        )
    return user


# ================================================================
# Get posts user = list[user]
# ================================================================


@router.get('/{username}/posts', response_model=list[posts.ReturnPostWithoutContent], status_code=200)
async def get_user_posts(username: str,
                         offset: int = 0,
                         limit: int = 10):
    """ Get a list of posts on page user profile (WITHOUT CONTENT) from db """

    posts_from_db = await get_posts_by_username(username=username, offset=offset * 10, limit=limit)

    result = posts_from_db.scalars().all()
    if not result:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail='Posts not found'
        )
    return result
