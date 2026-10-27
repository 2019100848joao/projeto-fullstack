import ulid
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DocumentType(Base):
    __tablename__ = "document_type"

    id: Mapped[str] = mapped_column(
        String(26),
        primary_key=True,
        default=lambda: ulid.new().str,
    )
    type: Mapped[str] = mapped_column(String(255))
