from os import getenv

from dotenv import load_dotenv
from fastapi_mail import ConnectionConfig

load_dotenv()


class Config:
    # Fragments url #############
    __db_name = getenv('DB_NAME')
    __db_pass = getenv('DB_PASS')
    __db_user = getenv('DB_USER')
    __db_host = getenv('DB_HOST')
    __db_port = getenv('DB_PORT')

    __es_host = getenv('ES_HOST')
    __es_port = getenv('ES_PORT')
    #############################

    postgres_url =\
        f'postgresql+asyncpg://{__db_user}:{__db_pass}@{__db_host}:{__db_port}/{__db_name}?async_fallback=True'

    jwt_secret = getenv('JWT_SECRET')
    jwt_algorithm = getenv('JWT_ALGORITHM')
    mail_token_expire_seconds = int(getenv('MAIL_TOKEN_EXPIRE_SECONDS'))
    access_token_expire_minutes = int(getenv('ACCESS_TOKEN_EXPIRE_MINUTES'))
    refresh_token_expire_days = int(getenv('REFRESH_TOKEN_EXPIRE_DAYS'))

    master_key = getenv('MASTER_KEY')

    retention_time_days = getenv('RETENTION_TIME_DAYS')
    rotation_size = getenv('ROTATION_SIZE')

    mail_conf = ConnectionConfig(
        MAIL_USERNAME=getenv('SMTP_USERNAME'),
        MAIL_PASSWORD=getenv('SMTP_PASSWORD'),
        MAIL_FROM=getenv('SMTP_FROM'),
        MAIL_PORT=int(getenv('SMTP_PORT')),
        MAIL_SERVER=getenv('SMTP_SERVER'),
        MAIL_STARTTLS=bool(int(getenv('SMTP_TLS'))),
        MAIL_SSL_TLS=bool(int(getenv('SMTP_SSL')))
    )

    redis_host = getenv('REDIS_HOST')
    redis_port = int(getenv('REDIS_PORT'))

    elasticsearch_url = f'http://{__es_host}:{__es_port}'
