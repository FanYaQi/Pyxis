# pylint: disable=C0103
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field


class ConfigMetadata(BaseModel):
    created_at: Optional[datetime] = Field(
        None, description="When the configuration was created"
    )
    author: Optional[str] = Field(None, description="Who created the configuration")
    schema_id: Optional[str] = Field(None, description="ID of the configuration schema")


class FileType(Enum):
    csv = "csv"
    shapefile = "shapefile"


class AttributeType(Enum):
    string = "string"
    integer = "integer"
    number = "number"
    boolean = "boolean"
    date = "date"
    datetime = "datetime"
    geometry = "geometry"


class Attribute(BaseModel):
    name: str = Field(description="Name of the attribute")
    units: Optional[str] = Field(None, description="Units of the attribute")
    description: Optional[str] = Field(None, description="Description of the attribute")
    type: AttributeType = Field(description="Type of the attribute")


class DataMetadata(BaseModel):
    name: str = Field(..., description="Human-readable name of the data source")
    description: Optional[str] = Field(
        None, description="Detailed description of the data source"
    )
    type: FileType = Field(..., description="Type of data source file")
    version: str = Field(..., description="Version of the data source")
    attributes: List[Attribute] = Field(
        description="List of attributes in the data source"
    )


class SpatialConfiguration(BaseModel):
    enabled: bool = Field(..., description="Whether the source contains spatial data")
    geometry_field: Optional[str] = Field(
        "geometry", description="Name of the field containing geometry data"
    )
    source_crs: Optional[str] = Field(
        "EPSG:4326", description="Coordinate reference system of the source data"
    )


class Csv(BaseModel):
    delimiter: str = Field(",", description="Field delimiter character")
    encoding: str = Field("utf-8", description="Character encoding of the file")
    header_row: int = Field(
        0, description="Row number containing column headers (0-based)", ge=0
    )


class Shapefile(BaseModel):
    encoding: str = Field("utf-8", description="Character encoding of the DBF file")
    layer_name: str = Field(
        "0", description="Name of the layer to use if multiple layers exist"
    )
    filter_attributes: List[str] = Field(
        [], description="List of attributes to keep from the shapefile"
    )


class FileSpecific(BaseModel):
    csv: Optional[Csv] = Field(None, description="Configuration specific to CSV files")
    shapefile: Optional[Shapefile] = Field(
        None, description="Configuration specific to Shapefile files"
    )


class Mapping(BaseModel):
    source_attribute: str = Field(
        ..., description="Name of the attribute in the source data"
    )
    target_attribute: str = Field(
        ..., description="Name of the corresponding OPGEE attribute"
    )


class DataEntryConfiguration(BaseModel):
    config_metadata: Optional[ConfigMetadata] = Field(
        None, description="Metadata about the configuration itself"
    )
    data_metadata: DataMetadata = Field(description="Information about the data source")
    spatial_configuration: Optional[SpatialConfiguration] = Field(
        None, description="Configuration for spatial data processing"
    )
    file_specific: Optional[FileSpecific] = Field(
        default=None, description="File format-specific configuration"
    )
    mappings: List[Mapping] = Field(
        ..., description="Mappings from source attributes to target OPGEE attributes"
    )

    def get_attribute_mapping(self) -> Dict[str, str]:
        """Get a dictionary mapping source attributes to target attributes"""
        return {
            mapping.source_attribute: mapping.target_attribute
            for mapping in self.mappings
        }

    def get_source_attribute_map(self) -> Dict[str, Attribute]:
        """Get a dictionary mapping source attributes to their metadata"""
        return {
            attribute.name: attribute for attribute in self.data_metadata.attributes
        }

    def get_attributes_metadata_map(self) -> Dict[str, Attribute]:
        """Get the data metadata"""
        if self.data_metadata is None:
            raise ValueError("Data metadata is not set")

        return {
            attribute.name: attribute for attribute in self.data_metadata.attributes
        }
