from enum import StrEnum


class EmailEventType(StrEnum):
    USER_REGISTERED = "user_registered"
    ROLE_TRANSITION_REQUESTED = "role_transition_requested"
    ROLE_TRANSITION_ADMIN_ALERT = "role_transition_admin_alert"
    ROLE_TRANSITION_APPROVED = "role_transition_approved"
    ROLE_TRANSITION_REJECTED = "role_transition_rejected"
