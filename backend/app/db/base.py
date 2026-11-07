# Import all the models here so Alembic can discover their metadata.
# Example: from app.models.user import User
from app.db.base_class import Base, SoftDeleteMixin, TimestampMixin

__all__ = ["Base", "SoftDeleteMixin", "TimestampMixin"]
