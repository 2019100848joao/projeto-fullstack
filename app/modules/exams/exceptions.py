class ExamError(Exception):
    pass


class ExamNotFoundError(ExamError):
    pass


class ExamAccessDeniedError(ExamError):
    pass


class InvalidExamStatusTransitionError(ExamError):
    pass
