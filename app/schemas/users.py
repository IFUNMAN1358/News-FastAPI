from typing import List

from fastapi import HTTPException
from pydantic import BaseModel, UUID4, validator, EmailStr
from starlette.status import HTTP_400_BAD_REQUEST

from app.schemas.regex.regex_users import RegexUsers


class RegisterUser(BaseModel):
    username: str
    email: EmailStr
    password: str
    repeat_password: str

    @validator('username')
    def validate_username_register(cls, v):
        if not v:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST,
                                detail='Field username cannot be empty')
        if not RegexUsers.verify_username(v):
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST,
                                detail='Username does not match: ^[a-zA-Z0-9_-]{5,20}$')
        return v

    @validator('password')
    def validate_password_register(cls, v):
        if not v:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST,
                                detail='Field password cannot be empty')
        if not RegexUsers.verify_password(v):
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST,
                                detail='Password does not match: ^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d@$!%*#?&]{6,}$')
        return v

    @validator('repeat_password')
    def validate_repeat_password_register(cls, v):
        if not v:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST,
                                detail='Field repeat password cannot be empty')
        if not RegexUsers.verify_password(v):
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST,
                                detail='Repeat password does not match:'
                                       ' ^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d@$!%*#?&]{6,}$')
        return v


class LoginUser(BaseModel):
    username_or_email: str
    password: str

    @validator('username_or_email')
    def validate_username_or_email_login(cls, v):
        if not v:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST,
                                detail='Field username/email cannot be empty')
        return v

    @validator('password')
    def validate_password_login(cls, v):
        if not v:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST,
                                detail='Field password cannot be empty')
        return v


class ReturnUser(BaseModel):
    UUID: UUID4
    username: str


class Username(BaseModel):
    username: str


class ElasticUser(BaseModel):
    username: str


class EmailSchema(BaseModel):
    email: List[EmailStr]


class AboutMe(BaseModel):
    description: str | None


class ChangeUsername(BaseModel):
    new_username: str
    password: str


class ChangeEmail(BaseModel):
    password: str
    new_email: EmailStr
    repeat_new_email: EmailStr


class ChangePassword(BaseModel):
    password: str
    repeat_password: str


class ReturnUserSearch(BaseModel):
    username: str
    likes: int


class ReturnFullUser(BaseModel):
    UUID: UUID4
    username: str
    about_me: str | None
    likes: int
    role: str
