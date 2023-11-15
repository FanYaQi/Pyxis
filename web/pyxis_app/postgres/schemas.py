from geoalchemy2.types import WKBElement
from geoalchemy2.shape import to_shape
from pydantic import BaseModel, Field, field_serializer


class ZhanFieldSchema(BaseModel):
    id: int = Field(description="Field ID")
    id_field: int = Field(description="Field ID")
    geometry: WKBElement | str = Field(
        description="The string representation of the field geometry."
    )
    product_ty: str | None = Field(description="Production type, oil or field.")
    number: int
    n_fldname: str | None = Field(description="Name of the field.")
    country: str | None
    sum_oil_pr: float = Field(description="Sum of the oil production (kBarrel).")
    sum_gor: float
    bcm_2012: float
    bcm_2013: float
    bcm_2014: float
    bcm_2015: float
    bcm_2016: float
    bcm_2017: float
    bcm_2018: float
    bcm_2019: float

    class Config:
        orm_mode = True
        arbitrary_types_allowed = True  # This is to avoid error created by Pydantic not able to recognize WKBElement as a type.

    @field_serializer("geometry")
    def serialize_geometry(self, geometry: WKBElement):
        return to_shape(geometry).wkt
