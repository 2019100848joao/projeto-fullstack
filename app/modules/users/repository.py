from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.core.database import SqlRepository
from app.modules.appointments.enums import AppointmentStatus
from app.modules.appointments.models import Appointment
from app.modules.auth.enums import UserRole
from app.modules.document_types.models import DocumentType
from app.modules.exams.enums import ExamStatus
from app.modules.exams.models import Exam
from app.modules.users.exceptions import DocumentAlreadyExistsError
from app.modules.users.models import User, UserDocument


class UserRepository(SqlRepository):
    def get_by_id(self, user_id: str) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        statement = select(User).where(User.email == email)
        return self.db.scalar(statement)

    def get_active_by_role(self, user_id: str, role: UserRole) -> User | None:
        statement = select(User).where(
            User.id == user_id,
            User.role == role.value,
            User.is_active.is_(True),
        )
        return self.db.scalar(statement)

    def has_open_doctor_work(self, user_id: str) -> bool:
        """Scheduled appointments or exams still waiting for this doctor's result."""
        open_appointment = select(Appointment.id).where(
            Appointment.doctor_id == user_id,
            Appointment.status == AppointmentStatus.SCHEDULED.value,
        )
        open_exam = select(Exam.id).where(
            Exam.doctor_id == user_id,
            Exam.status != ExamStatus.RESULT_AVAILABLE.value,
        )
        return bool(
            self.db.scalar(select(or_(open_appointment.exists(), open_exam.exists())))
        )

    def lock_active_admin_ids(self) -> list[str]:
        """Locks the active admins in a fixed order, so two concurrent demotions
        cannot both see another admin left and remove the last one."""
        statement = (
            select(User.id)
            .where(User.role == UserRole.ADMIN.value, User.is_active.is_(True))
            .order_by(User.id)
            .with_for_update()
        )
        return list(self.db.scalars(statement))

    def list_all(self, *, role: UserRole | None = None) -> list[User]:
        statement = select(User).order_by(User.full_name, User.id)
        if role is not None:
            statement = statement.where(User.role == role.value)
        return list(self.db.scalars(statement))

    def create(
        self,
        *,
        email: str,
        full_name: str,
        hashed_password: str,
        role: UserRole = UserRole.PATIENT,
    ) -> User:
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hashed_password,
            role=role.value,
        )
        self.db.add(user)
        self.db.flush()
        return user

    def get_document_type_by_id(self, type_id: str) -> DocumentType | None:
        return self.db.get(DocumentType, type_id)

    def get_document_by_user_and_type(
        self, user_id: str, type_id: str
    ) -> UserDocument | None:
        statement = select(UserDocument).where(
            UserDocument.user_id == user_id,
            UserDocument.type_id == type_id,
        )
        return self.db.scalar(statement)

    def create_user_documents(
        self,
        *,
        user_id: str,
        documents: list[tuple[str, str]],
    ) -> list[UserDocument]:
        created = [
            UserDocument(user_id=user_id, type_id=type_id, value=value)
            for type_id, value in documents
        ]
        self.db.add_all(created)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            for type_id, _ in documents:
                if self.get_document_by_user_and_type(user_id, type_id) is not None:
                    raise DocumentAlreadyExistsError from exc
            raise
        for document in created:
            self.db.refresh(document)
        return created
