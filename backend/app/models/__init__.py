"""Import all model modules so SQLAlchemy registers every table on Base.metadata."""

from app.models import artifacts, events, execution, notification, project, quality, user, validation  # noqa: F401
