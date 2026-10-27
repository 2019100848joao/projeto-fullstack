from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.modules.auth.routes import router as auth_router
from app.modules.document_types.routes import router as document_types_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(document_types_router)
api_router.include_router(health_router)
