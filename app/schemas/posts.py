from datetime import datetime

from fastapi import HTTPException
from pydantic import BaseModel, UUID4, validator
from starlette.status import HTTP_400_BAD_REQUEST

from app.schemas.regex.regex_posts import RegexPosts


class CreatePost(BaseModel):
    title: str
    content: str


    @validator('title')
    def validate_title_create(cls, v):
        if not v:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST,
                                detail='Field title cannot be empty')
        if not RegexPosts.verify_title(v):
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST,
                                detail='Title does not match: ^.{30,100}$')
        return v

    @validator('content')
    def validate_content_create(cls, v):
        if not v:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST,
                                detail='Field content cannot be empty')
        if not RegexPosts.verify_content(v):
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST,
                                detail='Content does not match: ^.{200,5000}$')
        return v


class ElasticPost(BaseModel):
    id: int
    title: str


class ReturnPostWithoutContent(BaseModel):
    id: int
    owner_UUID: UUID4
    owner_username: str
    title: str
    created_at: datetime
    likes: int


class ReturnFullPost(BaseModel):
    id: int
    owner_UUID: UUID4
    owner_username: str
    title: str
    content: str
    created_at: datetime
    likes: int
