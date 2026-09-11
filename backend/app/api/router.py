from fastapi import APIRouter

from app.api.routes import auth, search, workspace

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(workspace.router)
api_router.include_router(search.router)
