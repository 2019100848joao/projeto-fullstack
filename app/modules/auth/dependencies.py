from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.modules.auth.enums import UserRole
from app.modules.auth.models import User
from app.modules.auth.repository import UserRepository
from app.modules.auth.service import AuthService

bearer_scheme = HTTPBearer(auto_error=False)


DbSession = Annotated[Session, Depends(get_db)]
BearerCredentials = Annotated[
    HTTPAuthorizationCredentials | None,
    Depends(bearer_scheme),
]


def get_auth_service(db: DbSession) -> AuthService:
    return AuthService(UserRepository(db))


def get_current_user(
    credentials: BearerCredentials,
    db: DbSession,
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise credentials_exception from exc

    user_id = payload.get("sub")
    if not isinstance(user_id, str):
        raise credentials_exception

    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def require_roles(*allowed_roles: UserRole) -> Callable[[User], User]:
    allowed_role_values = {role.value for role in allowed_roles}

    def dependency(current_user: CurrentUserDep) -> User:
        if current_user.role not in allowed_role_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource",
            )

        return current_user

    return dependency


AdminUserDep = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
PatientUserDep = Annotated[User, Depends(require_roles(UserRole.PATIENT))]
DoctorUserDep = Annotated[User, Depends(require_roles(UserRole.DOCTOR))]
AttendantUserDep = Annotated[User, Depends(require_roles(UserRole.ATTENDANT))]
