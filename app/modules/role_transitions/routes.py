from collections.abc import Callable

from fastapi import APIRouter, HTTPException, status

from app.modules.auth.dependencies import AdminUserDep, CurrentUserDep
from app.modules.auth.exceptions import UserNotFoundError
from app.modules.role_transitions.dependencies import RoleTransitionServiceDep
from app.modules.role_transitions.enums import TransitionStatus
from app.modules.role_transitions.exceptions import (
    InvalidRoleTransitionError,
    PendingRoleTransitionExistsError,
    RoleTransitionAlreadyReviewedError,
    RoleTransitionNotFoundError,
    RoleTransitionPermissionError,
)
from app.modules.role_transitions.models import RoleTransitionRequest
from app.modules.role_transitions.schemas import (
    RoleTransitionCreate,
    RoleTransitionRead,
)

router = APIRouter(prefix="/role-transitions", tags=["role-transitions"])


def _execute_review(
    action: Callable[[], RoleTransitionRequest],
) -> RoleTransitionRequest:
    try:
        return action()
    except RoleTransitionPermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to review role transitions",
        ) from exc
    except (RoleTransitionNotFoundError, UserNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role transition request not found",
        ) from exc
    except RoleTransitionAlreadyReviewedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role transition request has already been reviewed",
        ) from exc


@router.post("", response_model=RoleTransitionRead, status_code=status.HTTP_201_CREATED)
def request_role_transition(
    payload: RoleTransitionCreate,
    current_user: CurrentUserDep,
    service: RoleTransitionServiceDep,
) -> RoleTransitionRequest:
    try:
        return service.request_transition(current_user=current_user, payload=payload)
    except InvalidRoleTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role transition is not valid for the current user role",
        ) from exc
    except PendingRoleTransitionExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already has a pending role transition request",
        ) from exc


@router.get("", response_model=list[RoleTransitionRead])
def list_role_transitions(
    _admin_user: AdminUserDep,
    service: RoleTransitionServiceDep,
    status: TransitionStatus | None = None,
) -> list[RoleTransitionRequest]:
    return service.list_requests(status=status)


@router.post("/{request_id}/approve", response_model=RoleTransitionRead)
def approve_role_transition(
    request_id: str,
    admin_user: AdminUserDep,
    service: RoleTransitionServiceDep,
) -> RoleTransitionRequest:
    return _execute_review(
        lambda: service.approve_transition(
            admin_user=admin_user,
            request_id=request_id,
        )
    )


@router.post("/{request_id}/reject", response_model=RoleTransitionRead)
def reject_role_transition(
    request_id: str,
    admin_user: AdminUserDep,
    service: RoleTransitionServiceDep,
) -> RoleTransitionRequest:
    return _execute_review(
        lambda: service.reject_transition(
            admin_user=admin_user,
            request_id=request_id,
        )
    )
