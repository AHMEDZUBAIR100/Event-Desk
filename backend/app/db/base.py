# Import all the models here so Alembic can discover their metadata.
from app.db.base_class import Base, SoftDeleteMixin, TimestampMixin
from app.models.audit import AuditLog
from app.models.booking import Booking
from app.models.category import Category
from app.models.event import Event
from app.models.notification import Notification
from app.models.review import Review
from app.models.tag import Tag, event_tags
from app.models.user import RefreshToken, User

__all__ = [
    "AuditLog",
    "Base",
    "Booking",
    "Category",
    "Event",
    "Notification",
    "RefreshToken",
    "Review",
    "SoftDeleteMixin",
    "Tag",
    "TimestampMixin",
    "User",
    "event_tags",
]
