from app.modules.auth.enums import UserRole
from app.modules.notifications.enums import EmailEventType
from app.modules.notifications.models import EmailNotification
from app.modules.notifications.repository import EmailNotificationRepository

ROLE_LABELS: dict[str, str] = {
    UserRole.ADMIN.value: "Administrador",
    UserRole.PATIENT.value: "Paciente",
    UserRole.DOCTOR.value: "Médico",
    UserRole.ATTENDANT.value: "Atendente",
}


def role_label(role: str) -> str:
    return ROLE_LABELS.get(role, role)


class NotificationService:
    def __init__(self, repository: EmailNotificationRepository) -> None:
        self.repository = repository

    def record_registration_email(
        self,
        *,
        recipient_email: str,
        full_name: str,
    ) -> EmailNotification:
        patient = role_label(UserRole.PATIENT.value)
        return self.repository.create(
            recipient_email=recipient_email,
            subject=f"Confirmação de cadastro como {patient}",
            body=(
                f"Olá, {full_name}. Sua conta foi criada com o perfil inicial "
                f"de {patient}."
            ),
            event_type=EmailEventType.USER_REGISTERED,
        )

    def record_transition_requested_emails(
        self,
        *,
        requester_email: str,
        requester_name: str,
        requested_role: str,
        admin_emails: list[str],
    ) -> list[EmailNotification]:
        role = role_label(requested_role)
        created: list[EmailNotification] = [
            self.repository.create(
                recipient_email=requester_email,
                subject=f"Solicitação de transição para {role} enviada",
                body=(
                    f"Olá, {requester_name}. Sua solicitação de transição para o "
                    f"cargo de {role} aguarda a aprovação do administrador."
                ),
                event_type=EmailEventType.ROLE_TRANSITION_REQUESTED,
            )
        ]
        for admin_email in admin_emails:
            created.append(
                self.repository.create(
                    recipient_email=admin_email,
                    subject=f"Novo pedido de transição de cargo: {requester_name}",
                    body=(
                        f"O usuário {requester_name} ({requester_email}) "
                        f"solicitou a transição para o cargo de {role}."
                    ),
                    event_type=EmailEventType.ROLE_TRANSITION_ADMIN_ALERT,
                )
            )
        return created

    def record_transition_decision_email(
        self,
        *,
        recipient_email: str,
        full_name: str,
        requested_role: str,
        approved: bool,
    ) -> EmailNotification:
        role = role_label(requested_role)
        decision = "aprovada" if approved else "recusada"
        return self.repository.create(
            recipient_email=recipient_email,
            subject=f"Transição para {role} {decision}",
            body=(
                f"Olá, {full_name}. Sua solicitação de transição para o cargo de "
                f"{role} foi {decision} pelo administrador."
            ),
            event_type=(
                EmailEventType.ROLE_TRANSITION_APPROVED
                if approved
                else EmailEventType.ROLE_TRANSITION_REJECTED
            ),
        )

    def list_emails(
        self,
        *,
        requester_email: str,
        is_admin: bool,
    ) -> list[EmailNotification]:
        target_email = None if is_admin else requester_email
        return self.repository.list_all(recipient_email=target_email)
