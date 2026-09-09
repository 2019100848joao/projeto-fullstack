from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.enums import UserRole
from app.modules.auth.models import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: str) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        statement = select(User).where(User.email == email)
        return self.db.scalar(statement)

    def update_role(self, user: User, role: UserRole) -> User:
        user.role = role.value
        self.db.commit()
        self.db.refresh(user)
        return user

    def create(
        self,
        *,
        email: str,
        full_name: str,
        hashed_password: str,
        role: UserRole = UserRole.PATIENT,
    ) -> User:
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hashed_password,
            role=role.value,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
