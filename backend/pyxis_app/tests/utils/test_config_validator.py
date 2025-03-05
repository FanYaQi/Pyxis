from unittest.mock import patch

# Test data
VALID_CONFIG = {
    "config_metadata": {
        "created_at": "2023-05-01T12:00:00Z",
        "author": "test_user",
        "schema_id": "oil_field_data_config_v0",
    },
    "data_metadata": {
        "name": "Test Source",
        "description": "Test data source",
        "type": "csv",
        "version": "1.0",
    },
    "spatial_configuration": {
        "enabled": True,
        "geometry_field": "geometry",
        "source_crs": "EPSG:4326",
    },
    "mappings": [
        {"source_attribute": "field_name", "target_attribute": "name"},
        {"source_attribute": "country", "target_attribute": "country"},
    ],
}

INVALID_CONFIG = {
    # Missing required fields
    "mappings": []
}


# Test config validator
def test_config_validator_valid():
    from pyxis_app.utils.config_validator import validate_config

    with patch("pyxis_app.utils.config_validator.load_schema", return_value={}):
        result = validate_config(VALID_CONFIG)
        assert result["valid"] is True
        assert len(result["errors"]) == 0


def test_config_validator_invalid():
    from pyxis_app.utils.config_validator import validate_config

    with patch("pyxis_app.utils.config_validator.load_schema", return_value={}):
        with patch("jsonschema.Draft7Validator.iter_errors", return_value=["Error 1"]):
            result = validate_config(INVALID_CONFIG)
            assert result["valid"] is False
            assert len(result["errors"]) > 0
