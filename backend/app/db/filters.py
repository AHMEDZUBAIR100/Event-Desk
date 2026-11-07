from typing import Any

from sqlalchemy import Select


def filter_active(statement: Select[Any], model: Any) -> Select[Any]:
    """Applies a filter to include only active (non-soft-deleted) records."""
    if hasattr(model, "deleted_at"):
        return statement.where(model.deleted_at.is_(None))
    return statement
