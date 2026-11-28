import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.modules.auth.service import AuthService
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

logger = logging.getLogger(__name__)


def ensure_base_admin(db: Session) -> User | None:
    if not settings.seed_admin_email or not settings.seed_admin_password:
        logger.warning(
            "Base admin seed skipped: SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD "
            "must be set outside the local environment"
        )
        return None

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
