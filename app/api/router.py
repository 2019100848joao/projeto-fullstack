from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.modules.auth.routes import router as auth_router
from app.modules.notifications.routes import router as notifications_router
from app.modules.role_transitions.routes import router as role_transitions_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(role_transitions_router)
api_router.include_router(notifications_router)
api_router.include_router(health_router)
