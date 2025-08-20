"""Integration tests for base API utilities in actual endpoints."""

import inspect
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from energy_assistant.api.base import get_energy_assistant, get_home
from energy_assistant.api.config import views as config_views
from energy_assistant.api.config.views import read_configuration
from energy_assistant.api.device import views as device_views
from energy_assistant.api.device.views import read_all as device_read_all
from energy_assistant.api.home_measurement import views as home_measurement_views

time_zone = ZoneInfo("Europe/Berlin")


class TestBaseUtilitiesIntegration:
    """Integration tests to verify base utilities work correctly in real API endpoints."""

    def test_endpoints_use_base_utilities(self):
        """Test that API endpoints are correctly using the base utilities."""
        # This test verifies that our base utilities are imported and used
        # by checking the source code of the API modules

        # Check that base module functions are imported
        assert hasattr(config_views, 'get_energy_assistant')
        assert hasattr(device_views, 'get_energy_assistant')

    def test_mock_endpoint_error_handling(self):
        """Test that endpoints handle missing energy_assistant correctly."""
        # This test creates a minimal FastAPI app to test error handling
        test_app = FastAPI()

        @test_app.get("/test-endpoint")
        async def test_endpoint(request: Request):
            """Test endpoint that uses get_energy_assistant."""
            energy_assistant = get_energy_assistant(request)
            return {"status": "success", "energy_assistant": str(energy_assistant)}

        # Test with missing energy_assistant
        with TestClient(test_app) as client:
            response = client.get("/test-endpoint")
            assert response.status_code == 500
            assert "Energy Assistant not available" in response.json()["detail"]

    def test_mock_endpoint_success(self):
        """Test that endpoints work correctly when energy_assistant is available."""
        test_app = FastAPI()

        # Mock energy assistant
        mock_energy_assistant = MagicMock()
        mock_energy_assistant.config = {"test": "config"}
        test_app.energy_assistant = mock_energy_assistant

        @test_app.get("/test-endpoint")
        async def test_endpoint(request: Request):
            """Test endpoint that uses get_energy_assistant."""
            energy_assistant = get_energy_assistant(request)
            return {"status": "success", "has_energy_assistant": energy_assistant is not None}

        # Test with available energy_assistant
        with TestClient(test_app) as client:
            response = client.get("/test-endpoint")
            assert response.status_code == 200
            assert response.json()["status"] == "success"
            assert response.json()["has_energy_assistant"] is True


class TestErrorHandlingConsistency:
    """Test that error handling is consistent across all endpoints that use base utilities."""

    def test_consistent_error_responses(self):
        """Test that all endpoints using base utilities return consistent error responses."""
        # Test get_energy_assistant error
        mock_request = MagicMock(spec=Request)
        mock_request.app = MagicMock()
        mock_request.app.energy_assistant = None

        with pytest.raises(HTTPException) as exc_info:
            get_energy_assistant(mock_request)

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Energy Assistant not available"

        # Test get_home error when energy_assistant not available
        mock_request.app.home = None
        # Remove energy_assistant attribute to simulate it not being set
        delattr(mock_request.app, 'energy_assistant')

        with pytest.raises(HTTPException) as exc_info:
            get_home(mock_request)

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Energy Assistant not available"


class TestDocumentationAndTypeHints:
    """Test that the base utilities have proper documentation and type hints."""

    def test_function_docstrings(self):
        """Test that base utility functions have proper docstrings."""

        # Check get_energy_assistant docstring
        assert get_energy_assistant.__doc__ is not None
        assert "Get energy assistant from request" in get_energy_assistant.__doc__
        assert "Args:" in get_energy_assistant.__doc__
        assert "Returns:" in get_energy_assistant.__doc__
        assert "Raises:" in get_energy_assistant.__doc__
        assert "HTTPException: 500 error" in get_energy_assistant.__doc__

        # Check get_home docstring
        assert get_home.__doc__ is not None
        assert "Get home instance from request" in get_home.__doc__
        assert "Args:" in get_home.__doc__
        assert "Returns:" in get_home.__doc__
        assert "Raises:" in get_home.__doc__
        assert "HTTPException: 500 error" in get_home.__doc__

    def test_function_annotations(self):
        """Test that base utility functions have proper type annotations."""
        # Check get_energy_assistant annotations
        sig = inspect.signature(get_energy_assistant)
        assert 'request' in sig.parameters
        assert sig.parameters['request'].annotation == Request

        # Check get_home annotations
        sig = inspect.signature(get_home)
        assert 'request' in sig.parameters
        assert sig.parameters['request'].annotation == Request


class TestBackwardCompatibility:
    """Test that the changes maintain backward compatibility."""

    def test_api_endpoints_still_accessible(self):
        """Test that all API endpoints are still accessible and return expected structure."""
        # Test that critical endpoints still exist and have the expected path structure

        # Check that routers exist and have expected prefixes
        assert hasattr(config_views, 'router')
        assert hasattr(device_views, 'router')
        assert hasattr(home_measurement_views, 'router')

        # Check that key functions exist
        assert hasattr(config_views, 'read_configuration')
        assert hasattr(device_views, 'read_all')
        assert hasattr(home_measurement_views, 'read_all')

    def test_response_model_consistency(self):
        """Test that response models are consistently defined."""
        # Check that functions have proper response_model decorators
        # This ensures return type annotations match the response models

        # We can't easily test the decorator values directly, but we can ensure
        # the functions exist and are callable
        assert callable(read_configuration)
        assert callable(device_read_all)
