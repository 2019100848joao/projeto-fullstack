from typing import Annotated

from fastapi import Depends

from app.modules.auth.dependencies import DbSession, require_roles
from app.modules.auth.enums import UserRole
from app.modules.auth.models import User
from app.modules.exams.repository import ExamRepository
from app.modules.exams.service import ExamService


def get_exam_service(db: DbSession) -> ExamService:
    return ExamService(ExamRepository(db))


ExamViewerDep = Annotated[
    User,
    Depends(
        require_roles(
            UserRole.ATTENDANT,
            UserRole.DOCTOR,
            UserRole.PATIENT,
            UserRole.ADMIN,
        )
    ),
]
ExamOperatorDep = Annotated[
    User,
    Depends(require_roles(UserRole.ATTENDANT, UserRole.ADMIN)),
]
