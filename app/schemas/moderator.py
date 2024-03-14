from pydantic import BaseModel


class RenameUsername(BaseModel):
    current_username: str
    new_username: str
