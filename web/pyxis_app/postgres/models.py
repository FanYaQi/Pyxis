from sqlalchemy import Column, Double, Integer, String, UniqueConstraint
from geoalchemy2 import Geometry

from .database import Base


class ZhanField(Base):
    __tablename__ = "zhan_global_field"

    id = Column(Integer, primary_key=True, nullable=False)
    id_field = Column(Integer)
    geometry = Column(Geometry("GEOMETRY", srid=4326))
    product_ty = Column(String)
    number = Column(Double)
    n_fldname = Column(String)
    country = Column(String)
    sum_oil_pr = Column(Double)
    sum_gor = Column(Double)
    bcm_2012 = Column(Double)
    bcm_2013 = Column(Double)
    bcm_2014 = Column(Double)
    bcm_2015 = Column(Double)
    bcm_2016 = Column(Double)
    bcm_2017 = Column(Double)
    bcm_2018 = Column(Double)
    bcm_2019 = Column(Double)

    __table_args__ = (UniqueConstraint("id_field", name="zhan_tm_field_id_field_key"),)
