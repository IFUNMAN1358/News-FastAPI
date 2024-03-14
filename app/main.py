from fastapi import FastAPI

from app.routers.auth import router as auth_router
from app.routers.account import router as account_router
from app.routers.posts import router as posts_router
from app.routers.authors import router as authors_router
from app.routers.moderator import router as moderator_router
from app.routers.admin import router as admin_router


app = FastAPI()


app.include_router(
    router=auth_router,
    prefix='/auth',
    tags=['Auth']
)

app.include_router(
    router=account_router,
    prefix='/account',
    tags=['Account']
)

app.include_router(
    router=posts_router,
    prefix='/posts',
    tags=["Posts"]
)

app.include_router(
    router=authors_router,
    prefix='/authors',
    tags=["Authors"]
)

app.include_router(
    router=moderator_router,
    prefix='/moderator',
    tags=["Moderator"]
)

app.include_router(
    router=admin_router,
    prefix='/admin',
    tags=["Admin"]
)
