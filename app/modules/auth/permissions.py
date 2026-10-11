from app.modules.auth.enums import UserRole
from app.modules.auth.models import User

ROLE_CHANGE_RULES: dict[UserRole, dict[UserRole, set[UserRole]]] = {
    UserRole.ADMIN: {
        UserRole.ADMIN: set(UserRole),
        UserRole.PATIENT: set(UserRole),
        UserRole.DOCTOR: set(UserRole),
        UserRole.ATTENDANT: set(UserRole),
    },
    UserRole.DOCTOR: {
        UserRole.ATTENDANT: {UserRole.PATIENT, UserRole.ATTENDANT},
    },
    UserRole.ATTENDANT: {
        UserRole.PATIENT: {UserRole.PATIENT, UserRole.ATTENDANT},
    },
}

APPOINTMENT_CREATORS = {UserRole.DOCTOR, UserRole.ATTENDANT}


class PermissionService:
    def user_has_any_role(self, user: User, roles: set[UserRole]) -> bool:
        return UserRole(user.role) in roles

    def can_create_appointment(self, user: User) -> bool:
        return self.user_has_any_role(user, APPOINTMENT_CREATORS)

    def can_change_user_role(
        self,
        *,
        current_user: User,
        target_user: User,
        new_role: UserRole,
    ) -> bool:
        current_role = UserRole(current_user.role)
        target_role = UserRole(target_user.role)
        allowed_target_roles = ROLE_CHANGE_RULES.get(current_role, {}).get(target_role)

        return allowed_target_roles is not None and new_role in allowed_target_roles
