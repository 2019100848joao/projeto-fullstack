from app.modules.notifications.enums import EmailEventType
from app.modules.notifications.models import EmailNotification
from app.modules.notifications.repository import EmailNotificationRepository


class NotificationService:
    def __init__(self, repository: EmailNotificationRepository) -> None:
        self.repository = repository

    def record_registration_email(
        self,
        *,
        recipient_email: str,
        full_name: str,
    ) -> EmailNotification:
        return self.repository.create(
            recipient_email=recipient_email,
            subject="Confirmacao de cadastro como Paciente",
            body=(
                f"Ola, {full_name}. Sua conta foi criada com o papel inicial "
                "de paciente."
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
        created: list[EmailNotification] = [
            self.repository.create(
                recipient_email=requester_email,
                subject=f"Solicitacao de transicao para {requested_role} enviada",
                body=(
                    f"Ola, {requester_name}. Sua solicitacao de transicao para "
                    f"o cargo '{requested_role}' aguarda aprovacao do admin."
                ),
                event_type=EmailEventType.ROLE_TRANSITION_REQUESTED,
            )
        ]
        for admin_email in admin_emails:
            created.append(
                self.repository.create(
                    recipient_email=admin_email,
                    subject=f"Novo pedido de transicao de cargo: {requester_name}",
                    body=(
                        f"O usuario {requester_name} ({requester_email}) "
                        f"solicitou transicao para o cargo '{requested_role}'."
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
        if approved:
            return self.repository.create(
                recipient_email=recipient_email,
                subject=f"Transicao para {requested_role} aprovada",
                body=(
                    f"Ola, {full_name}. Sua solicitacao de transicao para o "
                    f"cargo '{requested_role}' foi aprovada pelo administrador."
                ),
                event_type=EmailEventType.ROLE_TRANSITION_APPROVED,
            )

        return self.repository.create(
            recipient_email=recipient_email,
            subject=f"Transicao para {requested_role} recusada",
            body=(
                f"Ola, {full_name}. Sua solicitacao de transicao para o "
                f"cargo '{requested_role}' foi recusada pelo administrador."
            ),
            event_type=EmailEventType.ROLE_TRANSITION_REJECTED,
        )

    def list_emails(
        self,
        *,
        requester_email: str,
        is_admin: bool,
    ) -> list[EmailNotification]:
        target_email = None if is_admin else requester_email
        return self.repository.list_all(recipient_email=target_email)
