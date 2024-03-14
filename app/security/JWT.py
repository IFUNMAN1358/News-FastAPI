from datetime import datetime, timedelta

from jose import jwt

from app.config import Config


async def create_mail_token(username: str):
    to_encode = {}
    to_encode.update({"sub": str(username)})
    to_encode.update({'exp': datetime.utcnow() + timedelta(seconds=Config.mail_token_expire_seconds)})
    mail_token = jwt.encode(to_encode, Config.jwt_secret, algorithm=Config.jwt_algorithm)
    return mail_token


async def create_access_token(user_uuid):
    to_encode = {}
    to_encode.update({"sub": str(user_uuid)})
    to_encode.update({'exp': datetime.utcnow() + timedelta(minutes=Config.access_token_expire_minutes)})
    access_token = jwt.encode(to_encode, Config.jwt_secret, algorithm=Config.jwt_algorithm)
    return access_token


async def create_refresh_token(user_uuid):
    to_encode = {}
    to_encode.update({"sub": str(user_uuid)})
    to_encode.update({'exp': datetime.utcnow() + timedelta(days=Config.refresh_token_expire_days)})
    refresh_token = jwt.encode(to_encode, Config.jwt_secret, algorithm=Config.jwt_algorithm)
    return refresh_token
