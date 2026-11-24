from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.modules.auth.models import User
from app.modules.auth.repository import UserRepository
from app.modules.auth.service import AuthService


def ensure_base_admin(db: Session) -> User:
    service = AuthService(UserRepository(db))
    return service.ensure_base_admin(
        email=settings.seed_admin_email,
        full_name=settings.seed_admin_full_name,
        password=settings.seed_admin_password,
    )


def bootstrap_base_admin() -> None:
    db = SessionLocal()
    try:
        ensure_base_admin(db)
    finally:
        db.close()
