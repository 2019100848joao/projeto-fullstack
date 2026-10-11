from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.modules.appointments.routes import router as appointments_router
from app.modules.auth.routes import router as auth_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(appointments_router)
api_router.include_router(health_router)
