class RoleTransitionError(Exception):
    pass


class RoleTransitionNotFoundError(RoleTransitionError):
    pass


class RoleTransitionAlreadyReviewedError(RoleTransitionError):
    pass


class PendingRoleTransitionExistsError(RoleTransitionError):
    pass


class RoleTransitionPermissionError(RoleTransitionError):
    pass


class InvalidRoleTransitionError(RoleTransitionError):
    pass
