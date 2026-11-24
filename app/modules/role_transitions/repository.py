from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.role_transitions.enums import (
    TransitionStatus,
    TransitionTargetRole,
)
from app.modules.role_transitions.models import RoleTransitionRequest


class RoleTransitionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        user_id: str,
        requested_role: TransitionTargetRole,
    ) -> RoleTransitionRequest:
        transition_request = RoleTransitionRequest(
            user_id=user_id,
            requested_role=requested_role.value,
            status=TransitionStatus.PENDING.value,
        )
        self.db.add(transition_request)
        self.db.commit()
        self.db.refresh(transition_request)
        return transition_request

    def get_by_id(self, request_id: str) -> RoleTransitionRequest | None:
        return self.db.get(RoleTransitionRequest, request_id)

    def get_pending_by_user_id(self, user_id: str) -> RoleTransitionRequest | None:
        statement = select(RoleTransitionRequest).where(
            RoleTransitionRequest.user_id == user_id,
            RoleTransitionRequest.status == TransitionStatus.PENDING.value,
        )
        return self.db.scalar(statement)

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

    def save(
        self,
        transition_request: RoleTransitionRequest,
    ) -> RoleTransitionRequest:
        self.db.commit()
        self.db.refresh(transition_request)
        return transition_request
