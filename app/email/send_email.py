from fastapi_mail import MessageSchema, MessageType, FastMail

from app.config import Config
from app.schemas import users


async def send_email_code(mail: users.EmailSchema,
                          email_code: int,
                          body: str):
    message = MessageSchema(
        subject="NAMELESS PROJECT",
        recipients=mail.dict().get("email"),
        body=body + str(email_code),
        subtype=MessageType.html)

    fm = FastMail(Config.mail_conf)
    await fm.send_message(message)


async def send_email_info(mail: users.EmailSchema,
                          body: str):
    message = MessageSchema(
        subject="NAMELESS PROJECT",
        recipients=mail.dict().get("email"),
        body=body,
        subtype=MessageType.html)

    fm = FastMail(Config.mail_conf)
    await fm.send_message(message)