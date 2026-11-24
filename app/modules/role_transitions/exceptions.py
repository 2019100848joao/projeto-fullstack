class RoleTransitionError(Exception):
    pass


class RoleTransitionNotFoundError(RoleTransitionError):
    pass


class RoleTransitionAlreadyReviewedError(RoleTransitionError):
    pass


class InvalidRoleTransitionError(RoleTransitionError):
    pass
