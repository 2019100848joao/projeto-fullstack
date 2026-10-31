from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.auth.dependencies import CurrentUserDep, get_auth_service
from app.modules.auth.exceptions import (
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidCredentialsError,
    RoleChangeNotAllowedError,
    UserNotFoundError,
)
from app.modules.auth.schemas import Token, UserCreate, UserLogin, UserRoleUpdate
from app.modules.auth.service import AuthService
from app.modules.users.exceptions import (
    DocumentTypeNotFoundError,
    DocumentValueAlreadyExistsError,
)
from app.modules.users.models import User
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(user_create: UserCreate, auth_service: AuthServiceDep) -> User:
    try:
        return auth_service.register(user_create)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        ) from exc
    except DocumentTypeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document type not found",
        ) from exc
    except DocumentValueAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document value is already registered",
        ) from exc


@router.post("/login", response_model=Token)
def login(user_login: UserLogin, auth_service: AuthServiceDep) -> Token:
    try:
        return auth_service.login(email=user_login.email, password=user_login.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except InactiveUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        ) from exc


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: CurrentUserDep) -> User:
    return current_user


@router.patch("/{user_id}/role", response_model=UserRead)
def update_user_role(
    user_id: str,
    role_update: UserRoleUpdate,
    current_user: CurrentUserDep,
    auth_service: AuthServiceDep,
) -> User:
    try:
        return auth_service.update_user_role(
            current_user=current_user,
            target_user_id=user_id,
            new_role=role_update.role,
        )
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        ) from exc
    except RoleChangeNotAllowedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to change this user role",
        ) from exc
