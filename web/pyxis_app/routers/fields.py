from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.sql import text
from sqlalchemy.orm import Session

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

@router.get("/query_nearest_fields/", response_model=list[ZhanFieldSchema])
def find_nearest_fields(
    latitude: float,
    longitude: float,
    ring_size: int = 100,
    limit: int = 10,
    db: Session = Depends(get_postgres_db),
):
    """This API finds the nearest n fields based on latitude and longitude."""
    # Your SQL code to find the nearest fields based on latitude and longitude

    # Assuming your SQL code returns results in a variable called "nearest_fields"
    sqlText = text(f"""
                With re as(
                    WITH input_h3 AS (
                        SELECT h3_lat_lng_to_cell(Point({longitude}, {latitude}),9)::h3index AS h3_index
                    ),
                    k_ring_cells AS (
                        SELECT
                            h3_grid_disk(h3_index, {ring_size}) AS k_ring_cell
                        FROM
                            input_h3
                    )
                    select distinct on (z.id)
                        k_ring_cells.k_ring_cell,
                        z.id AS zhan_field_id,
                        h3_grid_distance(input_h3.h3_index, k_ring_cells.k_ring_cell) AS grid_distance
                    FROM
                        k_ring_cells
                    JOIN
                        zhan_global_h3_9 z ON k_ring_cells.k_ring_cell = z.h3_index
                    JOIN
                        input_h3 ON true
                    ORDER BY
                        z.id, grid_distance
                    )
                select zhan.*
                from re
                left join zhan_global_field zhan on re.zhan_field_id = zhan.id_field 
                order by re.grid_distance
                limit {limit};
                   """)
    results = db.query(ZhanField).from_statement(sqlText).all()

    if not results:
        raise HTTPException(
            status_code=404, detail="No fields found near the specified location"
        )

    return results
