from pydantic import BaseModel, EmailStr, UUID4


class AdminCreateUser(BaseModel):
    username: str
    email: EmailStr
    password: str
    repeat_password: str
    role: str = 'user'


class ReturnFullUserEmail(BaseModel):
    UUID: UUID4
    username: str
    email: str
    about_me: str | None
    likes: int
    role: str
