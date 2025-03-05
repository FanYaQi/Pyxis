"""
Data source service
"""
from sqlalchemy.orm import Session

from pyxis_app.postgres.models.user import User
from pyxis_app.postgres.models.data_source import DataSourceMeta


# Check if user has access to a data source
async def check_data_source_access(
    data_source_id: int, user: User, db: Session
) -> bool:
    """Check if a user has access to a specific data source"""
    # Superusers have access to everything
    if user.is_superuser:
        return True

    # Check user's data sources
    data_source = (
        db.query(DataSourceMeta)
        .filter(
            DataSourceMeta.id == data_source_id, DataSourceMeta.users.any(id=user.id)
        )
        .first()
    )

    return data_source is not None
