from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

from app.elasticsearch.url import elastic
from app.postgres.crud import get_posts_by_ids, get_posts_without_search_query, get_posts_user
from app.postgres.engine import get_db
from app.postgres.tables import Post, Like, User
from app.schemas import users
from app.schemas import posts
from app.security.authz import get_current_user


router = APIRouter()


# ================================================================
# Full-text search with elasticsearch and postgres = list[post]
# ================================================================


@router.get('/', response_model=list[posts.ReturnPostWithoutContent], status_code=200)
async def get_posts_with_search(query: str = None,
                                offset: int = 0,
                                limit: int = 10):
    """ Get a list of posts (WITHOUT CONTENT) from db with search query / without search query """
    # If user has entered a search query
    if query:
        response = await elastic.search(index='posts', body={
            "query": {
                "match": {
                    "title": {
                        "query": query,
                        "analyzer": "custom_analyzer",
                    }
                }
            }
        })
        ids_posts = [post['_source']['id'] for post in response['hits']['hits']]
        posts_from_db = await get_posts_by_ids(ids=ids_posts, offset=offset * 10, limit=limit)

    # Else, if user has not entered a search query
    else:
        posts_from_db = await get_posts_without_search_query(offset=offset * 10, limit=limit)

    # Checking existence for posts
    result = posts_from_db.scalars().all()
    if not result:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail='Posts not found'
        )
    return result


# ================================================================
# Get my posts = list[post]
# ================================================================


@router.get('/my-posts', response_model=list[posts.ReturnPostWithoutContent], status_code=200)
async def get_my_posts(offset: int = 0,
                       limit: int = 10,
                       current_user: users.ReturnUser = Depends(get_current_user)):
    """ Get a list of posts AUTHX USER (WITHOUT CONTENT) from db """
    posts_from_db = await get_posts_user(user_id=current_user.UUID,
                                         offset=offset * 10,
                                         limit=limit)

    result = posts_from_db.scalars().all()
    if not result:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail='Posts not found'
        )
    return result


# ================================================================
# Open post = post
# ================================================================


@router.get('/{post_id}', response_model=posts.ReturnFullPost, status_code=200)
async def open_post(post_id: int,
                    db: AsyncSession = Depends(get_db)):
    """ Return full post (WITH CONTENT) from postgres """
    post = await db.scalar(select(Post).where(Post.id == post_id))
    if not post:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail='Posts not found'
        )
    return post


# ================================================================
# Create/delete/update post funcs
# ================================================================


@router.post('/', response_model=posts.ReturnFullPost, status_code=201)
async def create_post(input_post: posts.CreatePost,
                      db: AsyncSession = Depends(get_db),
                      current_user: users.ReturnUser = Depends(get_current_user)):
    """ User can create a new post """

    # Creating post in postgres
    post = Post(owner_UUID=current_user.UUID,
                owner_username=current_user.username,
                title=input_post.title,
                content=input_post.content)
    try:
        db.add(post)
        await db.commit()
    except:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail='You already have a post with this title or content'
        )

    # Creating post in elasticsearch
    await elastic.index(index='posts', document=posts.ElasticPost(id=post.id,
                                                                  title=post.title).dict())
    return posts.ReturnFullPost(id=post.id, owner_UUID=current_user.UUID, owner_username=current_user.username,
                                title=post.title, content=post.content, created_at=post.created_at, likes=post.likes)


@router.delete('/{post_id}', status_code=200)
async def delete_post(post_id: int,
                      db: AsyncSession = Depends(get_db),
                      current_user: users.ReturnUser = Depends(get_current_user)):
    """ User can delete his post """

    # Deleting post in postgres
    post = await db.scalar(select(Post).where(and_(Post.id == post_id, Post.owner_UUID == current_user.UUID)))
    if post is None:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail='Post not found'
        )

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
    return {'detail': 'Post have been successfully deleted'}


@router.put('/{post_id}', response_model=posts.ReturnFullPost, status_code=201)
async def update_post(post_id: int,
                      input_post: posts.CreatePost,
                      db: AsyncSession = Depends(get_db),
                      current_user: users.ReturnUser = Depends(get_current_user)):
    """ User can update his post """

    # Updating post in postgres
    post = await db.scalar(select(Post).where(and_(Post.id == post_id, Post.owner_UUID == current_user.UUID)))
    if post is None:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail='Post not found'
        )
    await db.execute(
        update(Post)
        .where(and_(Post.id == post_id, Post.owner_UUID == current_user.UUID))
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
    return posts.ReturnFullPost(id=post.id, owner_UUID=current_user.UUID, owner_username=current_user.username,
                                title=post.title, content=post.content, created_at=post.created_at, likes=post.likes)


# ================================================================
# Like/unlike func
# ================================================================


@router.put("/{post_id}/like", response_model=posts.ReturnFullPost, status_code=201)
async def like_or_unlike_post(post_id: int,
                              current_user: users.ReturnUser = Depends(get_current_user),
                              db: AsyncSession = Depends(get_db)):

    post = await db.scalar(select(Post).where(Post.id == post_id))

    if post is None:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail='Post not found'
        )

    owner = await db.scalar(select(User).where(User.UUID == post.owner_UUID))

    if owner is None:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail='User not found'
        )

    existing_like = await db.scalar(select(Like).where(Like.user_UUID == current_user.UUID,
                                                       Like.post_id == post_id))
    if existing_like:
        await db.delete(existing_like)
        post.likes -= 1
        owner.likes -= 1
    else:
        like = Like(user_UUID=current_user.UUID,
                    post_id=post_id)
        db.add(like)
        post.likes += 1
        owner.likes += 1

    await db.commit()

    return posts.ReturnFullPost(id=post.id, owner_UUID=post.owner_UUID, owner_username=post.owner_username,
                                title=post.title, content=post.content, created_at=post.created_at, likes=post.likes)
