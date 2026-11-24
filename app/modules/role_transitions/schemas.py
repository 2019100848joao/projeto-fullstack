from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.role_transitions.enums import TransitionStatus, TransitionTargetRole


class RoleTransitionCreate(BaseModel):
    requested_role: TransitionTargetRole

    model_config = ConfigDict(extra="forbid")


class RoleTransitionRead(BaseModel):
    id: str
    user_id: str
    requested_role: TransitionTargetRole
    status: TransitionStatus
    created_at: datetime
    reviewed_by_id: str | None
    reviewed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
