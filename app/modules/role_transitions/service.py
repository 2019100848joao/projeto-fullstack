from datetime import UTC, datetime

from app.modules.auth.enums import UserRole
from app.modules.auth.exceptions import UserNotFoundError
from app.modules.auth.models import User
from app.modules.auth.repository import UserRepository
from app.modules.notifications.service import NotificationService
from app.modules.role_transitions.enums import TransitionStatus
from app.modules.role_transitions.exceptions import (
    InvalidRoleTransitionError,
    PendingRoleTransitionExistsError,
    RoleTransitionAlreadyReviewedError,
    RoleTransitionNotFoundError,
    RoleTransitionPermissionError,
)
from app.modules.role_transitions.models import RoleTransitionRequest
from app.modules.role_transitions.repository import RoleTransitionRepository
from app.modules.role_transitions.schemas import RoleTransitionCreate


class RoleTransitionService:
    def __init__(
        self,
        *,
        repository: RoleTransitionRepository,
        user_repository: UserRepository,
        notification_service: NotificationService,
    ) -> None:
        self.repository = repository
        self.user_repository = user_repository
        self.notification_service = notification_service

    def request_transition(
        self,
        *,
        current_user: User,
        payload: RoleTransitionCreate,
    ) -> RoleTransitionRequest:
        if (
            current_user.role == UserRole.ADMIN.value
            or current_user.role == payload.requested_role.value
        ):
            raise InvalidRoleTransitionError

        if self.repository.get_pending_by_user_id(current_user.id) is not None:
            raise PendingRoleTransitionExistsError

        transition_request = self.repository.create(
            user_id=current_user.id,
            requested_role=payload.requested_role,
        )

        admins = self.user_repository.list_all(role=UserRole.ADMIN)
        admin_emails = [admin.email for admin in admins if admin.is_active]

        self.notification_service.record_transition_requested_emails(
            requester_email=current_user.email,
            requester_name=current_user.full_name,
            requested_role=payload.requested_role.value,
            admin_emails=admin_emails,
        )

        return transition_request

    def list_requests(
        self,
        *,
        status: TransitionStatus | None = None,
    ) -> list[RoleTransitionRequest]:
        return self.repository.list_all(status=status)

    def approve_transition(
        self,
        *,
        admin_user: User,
        request_id: str,
    ) -> RoleTransitionRequest:
        return self._review_transition(
            admin_user=admin_user,
            request_id=request_id,
            approve=True,
        )

    def reject_transition(
        self,
        *,
        admin_user: User,
        request_id: str,
    ) -> RoleTransitionRequest:
        return self._review_transition(
            admin_user=admin_user,
            request_id=request_id,
            approve=False,
        )

    def _review_transition(
        self,
        *,
        admin_user: User,
        request_id: str,
        approve: bool,
    ) -> RoleTransitionRequest:
        if admin_user.role != UserRole.ADMIN.value:
            raise RoleTransitionPermissionError

        transition_request = self.repository.get_by_id(request_id)
        if transition_request is None:
            raise RoleTransitionNotFoundError

        if transition_request.status != TransitionStatus.PENDING.value:
            raise RoleTransitionAlreadyReviewedError

        target_user = self.user_repository.get_by_id(transition_request.user_id)
        if target_user is None:
            raise UserNotFoundError

        transition_request.status = (
            TransitionStatus.APPROVED.value
            if approve
            else TransitionStatus.REJECTED.value
        )
        transition_request.reviewed_by_id = admin_user.id
        transition_request.reviewed_at = datetime.now(UTC)

        if approve:
            self.user_repository.update_role(
                target_user,
                UserRole(transition_request.requested_role),
            )

        saved_request = self.repository.save(transition_request)

        self.notification_service.record_transition_decision_email(
            recipient_email=target_user.email,
            full_name=target_user.full_name,
            requested_role=transition_request.requested_role,
            approved=approve,
        )

        return saved_request
