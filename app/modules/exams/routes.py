from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.modules.exams.dependencies import (
    ExamOperatorDep,
    ExamViewerDep,
    ResultViewerDep,
    get_exam_service,
)
from app.modules.exams.enums import ExamStatus
from app.modules.exams.exceptions import (
    ExamAccessDeniedError,
    ExamNotFoundError,
    InvalidExamStatusTransitionError,
)
from app.modules.exams.models import Exam
from app.modules.exams.schemas import ExamRead, ExamResultCreate, ExamSchedule
from app.modules.exams.service import ExamService

router = APIRouter(prefix="/exams", tags=["exams"])

ExamServiceDep = Annotated[ExamService, Depends(get_exam_service)]

NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Exam not found",
)
ACCESS_DENIED = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="You do not have permission to access this exam",
)
INVALID_TRANSITION = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail="Exam status does not allow this operation",
)


@router.get(
    "",
    response_model=list[ExamRead],
    summary="List exams visible to the authenticated user",
)
def list_exams(
    current_user: ExamViewerDep,
    service: ExamServiceDep,
    exam_status: Annotated[ExamStatus | None, Query(alias="status")] = None,
    patient_id: str | None = None,
) -> list[Exam]:
    return service.list_exams(
        current_user=current_user,
        status=exam_status,
        patient_id=patient_id,
    )


@router.get(
    "/results",
    response_model=list[ExamRead],
    summary="List available exam results (patient, doctor, admin)",
)
def list_results(
    current_user: ResultViewerDep,
    service: ExamServiceDep,
    patient_id: str | None = None,
) -> list[Exam]:
    return service.list_results(current_user=current_user, patient_id=patient_id)


@router.get(
    "/{exam_id}",
    response_model=ExamRead,
    summary="Exam details visible to the authenticated user",
)
def read_exam(
    exam_id: str,
    current_user: ExamViewerDep,
    service: ExamServiceDep,
) -> Exam:
    try:
        return service.get_exam(current_user=current_user, exam_id=exam_id)
    except ExamNotFoundError as exc:
        raise NOT_FOUND from exc
    except ExamAccessDeniedError as exc:
        raise ACCESS_DENIED from exc


@router.post(
    "/{exam_id}/schedule",
    response_model=ExamRead,
    summary="Schedule a requested exam (attendant, admin)",
)
def schedule_exam(
    exam_id: str,
    exam_schedule: ExamSchedule,
    current_user: ExamOperatorDep,
    service: ExamServiceDep,
) -> Exam:
    try:
        return service.schedule(
            exam_id=exam_id,
            scheduled_at=exam_schedule.scheduled_at,
        )
    except ExamNotFoundError as exc:
        raise NOT_FOUND from exc
    except InvalidExamStatusTransitionError as exc:
        raise INVALID_TRANSITION from exc


@router.post(
    "/{exam_id}/perform",
    response_model=ExamRead,
    summary="Mark a scheduled exam as performed (attendant, admin)",
)
def perform_exam(
    exam_id: str,
    current_user: ExamOperatorDep,
    service: ExamServiceDep,
) -> Exam:
    try:
        return service.mark_performed(exam_id=exam_id)
    except ExamNotFoundError as exc:
        raise NOT_FOUND from exc
    except InvalidExamStatusTransitionError as exc:
        raise INVALID_TRANSITION from exc


@router.post(
    "/{exam_id}/result",
    response_model=ExamRead,
    summary="Register the text result of a performed exam (attendant, admin)",
)
def register_exam_result(
    exam_id: str,
    result_create: ExamResultCreate,
    current_user: ExamOperatorDep,
    service: ExamServiceDep,
) -> Exam:
    try:
        return service.register_result(
            exam_id=exam_id,
            result=result_create.result,
        )
    except ExamNotFoundError as exc:
        raise NOT_FOUND from exc
    except InvalidExamStatusTransitionError as exc:
        raise INVALID_TRANSITION from exc
