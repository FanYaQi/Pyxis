from fastapi import APIRouter, Depends, HTTPException

from pyxis_app.postgres.schemas import ZhanFieldSchema
from pyxis_app.postgres.database import SessionLocal
from pyxis_app.postgres.models import ZhanField
from pyxis_app.dependencies import get_postgres_db

router = APIRouter(
    prefix="/fields",
    tags=["fields"],
    # dependencies=[Depends(get_postgres_db)],
    responses={404: {"description": "Not found"}},
)


@router.get("/query_by_country/", response_model=list[ZhanFieldSchema])
def query_by_country(
    country: str,
    skip: int = 0,
    limit: int = 10,
    db: SessionLocal = Depends(get_postgres_db),
):
    """This API queries the Pyxis database by country name.

    Please make sure the first letter is capitalized.
    For example, `China` instead of `china`."""
    country_name = country

    # Query the database for records with the specified country name
    results = (
        db.query(ZhanField)
        .filter(ZhanField.country == country_name)
        .offset(skip)
        .limit(limit)
        .all()
    )

    if not results:
        raise HTTPException(
            status_code=200, detail="No records found for the specified country"
        )

    return results
