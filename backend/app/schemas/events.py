import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.event import EventStatus


class EventSortField(str, Enum):
    """Allowed catalogue sort columns."""

    DATE = "date"
    PRICE = "price"


class SortOrder(str, Enum):
    """Allowed sort directions."""

    ASC = "asc"
    DESC = "desc"


# ---------------------------------------------------------------------------
# Taxonomy schemas
# ---------------------------------------------------------------------------


class CategoryCreate(BaseModel):
    """Payload for creating a category."""

    name: str = Field(..., min_length=1, max_length=100)
    slug: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None


class CategoryRef(BaseModel):
    """Minimal category representation embedded in events."""

    id: uuid.UUID
    name: str
    slug: str

    model_config = ConfigDict(from_attributes=True)


class CategoryRead(CategoryRef):
    """Full category representation."""

    description: str | None = None
    created_at: datetime
    updated_at: datetime


class TagCreate(BaseModel):
    """Payload for creating a tag."""

    name: str = Field(..., min_length=1, max_length=50)
    slug: str | None = Field(default=None, min_length=1, max_length=60)


class TagRef(BaseModel):
    """Minimal tag representation embedded in events."""

    id: uuid.UUID
    name: str
    slug: str

    model_config = ConfigDict(from_attributes=True)


class TagRead(TagRef):
    """Full tag representation."""

    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Event schemas
# ---------------------------------------------------------------------------


class OrganizerRef(BaseModel):
    """Public organizer summary embedded in events."""

    id: uuid.UUID
    full_name: str

    model_config = ConfigDict(from_attributes=True)


class EventBase(BaseModel):
    """Fields shared by event create and read schemas."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    venue: str = Field(..., min_length=1, max_length=255)
    starts_at: datetime
    price: Decimal = Field(..., ge=0, max_digits=10, decimal_places=2)
    total_tickets: int = Field(..., ge=0)


class EventCreate(EventBase):
    """Payload for creating an event."""

    category_id: uuid.UUID | None = None
    status: EventStatus = EventStatus.DRAFT
    tag_ids: list[uuid.UUID] = Field(default_factory=list)

    @field_validator("status")
    @classmethod
    def _restrict_creation_status(cls, value: EventStatus) -> EventStatus:
        """Only draft and published events may be created."""
        if value not in (EventStatus.DRAFT, EventStatus.PUBLISHED):
            raise ValueError("New events must have status 'draft' or 'published'.")
        return value


#: Event fields that are non-nullable in the database. Explicit ``null`` in a
#: PATCH payload is rejected for these fields; only ``category_id`` may be nulled.
_NON_NULLABLE_PATCH_FIELDS = (
    "title",
    "description",
    "venue",
    "starts_at",
    "price",
    "total_tickets",
    "status",
    "tag_ids",
)


class EventUpdate(BaseModel):
    """Payload for partially updating an event.

    Omitted fields are left unchanged. ``category_id: null`` clears the
    category; explicit ``null`` for any other field is a validation error.
    """

    category_id: uuid.UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1)
    venue: str | None = Field(default=None, min_length=1, max_length=255)
    starts_at: datetime | None = None
    price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    total_tickets: int | None = Field(default=None, ge=0)
    status: EventStatus | None = None
    tag_ids: list[uuid.UUID] | None = None

    @model_validator(mode="after")
    def _reject_explicit_nulls(self) -> "EventUpdate":
        """Reject explicit ``null`` for non-nullable event fields."""
        for field_name in _NON_NULLABLE_PATCH_FIELDS:
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"Field '{field_name}' may not be null.")
        return self


class EventRead(EventBase):
    """Event representation returned by the API."""

    id: uuid.UUID
    organizer_id: uuid.UUID
    organizer: OrganizerRef
    category_id: uuid.UUID | None = None
    category: CategoryRef | None = None
    tickets_available: int
    status: EventStatus
    tags: list[TagRef] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EventDetailRead(EventRead):
    """Detailed event representation (reviews summary arrives in Day 4)."""


class EventListResponse(BaseModel):
    """Paginated public catalogue response envelope."""

    items: list[EventRead]
    total: int
    page: int
    size: int
