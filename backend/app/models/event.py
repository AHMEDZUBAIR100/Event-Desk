import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.booking import Booking
    from app.models.category import Category
    from app.models.review import Review
    from app.models.tag import Tag
    from app.models.user import User


class EventStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class Event(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organizer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    venue: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    total_tickets: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    tickets_available: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    status: Mapped[EventStatus] = mapped_column(
        Enum(
            EventStatus,
            name="event_status_enum",
            native_enum=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=EventStatus.DRAFT,
    )

    # Relationships
    organizer: Mapped["User"] = relationship(
        "User",
        back_populates="organized_events",
    )
    category: Mapped["Category | None"] = relationship(
        "Category",
        back_populates="events",
    )
    tags: Mapped[list["Tag"]] = relationship(
        "Tag",
        secondary="event_tags",
        back_populates="events",
    )
    bookings: Mapped[list["Booking"]] = relationship(
        "Booking",
        back_populates="event",
    )
    reviews: Mapped[list["Review"]] = relationship(
        "Review",
        back_populates="event",
    )

    __table_args__ = (
        CheckConstraint(
            "tickets_available >= 0 AND tickets_available <= total_tickets",
            name="ck_events_tickets_available",
        ),
        CheckConstraint(
            "total_tickets >= 0",
            name="ck_events_total_tickets_positive",
        ),
        CheckConstraint(
            "price >= 0",
            name="ck_events_price_non_negative",
        ),
        Index(
            "ix_events_active_catalog",
            "status",
            "starts_at",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_events_organizer_id",
            "organizer_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_events_category_id",
            "category_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )
