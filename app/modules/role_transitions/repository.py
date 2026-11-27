from sqlalchemy import select

from app.core.database import SqlRepository
from app.modules.role_transitions.enums import (
    TransitionStatus,
    TransitionTargetRole,
)
from app.modules.role_transitions.models import RoleTransitionRequest


class RoleTransitionRepository(SqlRepository):
    def create(
        self,
        *,
        user_id: str,
        requested_role: TransitionTargetRole,
    ) -> RoleTransitionRequest:
        """Raises ``IntegrityError`` if the user already has a pending request."""
        transition_request = RoleTransitionRequest(
            user_id=user_id,
            requested_role=requested_role.value,
            status=TransitionStatus.PENDING.value,
        )
        self.db.add(transition_request)
        self.db.flush()
        return transition_request

    def get_by_id(
        self,
        request_id: str,
        *,
        for_update: bool = False,
    ) -> RoleTransitionRequest | None:
        return self.db.get(
            RoleTransitionRequest,
            request_id,
            with_for_update=for_update,
        )

    def list_all(
        self,
        *,
        status: TransitionStatus | None = None,
    ) -> list[RoleTransitionRequest]:
        statement = select(RoleTransitionRequest).order_by(
            RoleTransitionRequest.created_at.desc()
        )
        if status is not None:
            statement = statement.where(RoleTransitionRequest.status == status.value)
        return list(self.db.scalars(statement))
