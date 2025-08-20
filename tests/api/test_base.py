"""Tests for the base API utilities."""

import pytest
from fastapi import HTTPException, Request
from unittest.mock import MagicMock

from energy_assistant.api.base import get_energy_assistant, get_home


class TestGetEnergyAssistant:
    """Tests for get_energy_assistant function."""

    def test_get_energy_assistant_success(self):
        """Test get_energy_assistant when energy_assistant is available."""
        # Arrange
        mock_energy_assistant = MagicMock()
        mock_app = MagicMock()
        mock_app.energy_assistant = mock_energy_assistant
        mock_request = MagicMock(spec=Request)
        mock_request.app = mock_app

        # Act
        result = get_energy_assistant(mock_request)

        # Assert
        assert result == mock_energy_assistant

    def test_get_energy_assistant_not_available(self):
        """Test get_energy_assistant when energy_assistant is not available."""
        # Arrange
        mock_app = MagicMock()
        # energy_assistant attribute doesn't exist
        del mock_app.energy_assistant
        mock_request = MagicMock(spec=Request)
        mock_request.app = mock_app

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            get_energy_assistant(mock_request)
        
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Energy Assistant not available"

    def test_get_energy_assistant_none(self):
        """Test get_energy_assistant when energy_assistant is None."""
        # Arrange
        mock_app = MagicMock()
        mock_app.energy_assistant = None
        mock_request = MagicMock(spec=Request)
        mock_request.app = mock_app

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            get_energy_assistant(mock_request)
        
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Energy Assistant not available"


class TestGetHome:
    """Tests for get_home function."""

    def test_get_home_directly_available(self):
        """Test get_home when home is directly available on request.app."""
        # Arrange
        mock_home = MagicMock()
        mock_app = MagicMock()
        mock_app.home = mock_home
        mock_request = MagicMock(spec=Request)
        mock_request.app = mock_app

        # Act
        result = get_home(mock_request)

        # Assert
        assert result == mock_home

    def test_get_home_from_energy_assistant(self):
        """Test get_home when home is available through energy_assistant."""
        # Arrange
        mock_home = MagicMock()
        mock_energy_assistant = MagicMock()
        mock_energy_assistant.home = mock_home
        mock_app = MagicMock()
        mock_app.home = None  # home not directly available
        mock_app.energy_assistant = mock_energy_assistant
        mock_request = MagicMock(spec=Request)
        mock_request.app = mock_app

        # Act
        result = get_home(mock_request)

        # Assert
        assert result == mock_home

    def test_get_home_energy_assistant_not_available(self):
        """Test get_home when energy_assistant is not available."""
        # Arrange
        mock_app = MagicMock()
        mock_app.home = None
        # energy_assistant attribute doesn't exist
        del mock_app.energy_assistant
        mock_request = MagicMock(spec=Request)
        mock_request.app = mock_app

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            get_home(mock_request)
        
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Energy Assistant not available"

    def test_get_home_energy_assistant_none(self):
        """Test get_home when energy_assistant is None."""
        # Arrange
        mock_app = MagicMock()
        mock_app.home = None
        mock_app.energy_assistant = None
        mock_request = MagicMock(spec=Request)
        mock_request.app = mock_app

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            get_home(mock_request)
        
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Energy Assistant not available"

    def test_get_home_no_home_attribute(self):
        """Test get_home when home attribute doesn't exist, uses energy_assistant.home."""
        # Arrange
        mock_home = MagicMock()
        mock_energy_assistant = MagicMock()
        mock_energy_assistant.home = mock_home
        mock_app = MagicMock()
        # home attribute doesn't exist
        del mock_app.home
        mock_app.energy_assistant = mock_energy_assistant
        mock_request = MagicMock(spec=Request)
        mock_request.app = mock_app

        # Act
        result = get_home(mock_request)

        # Assert
        assert result == mock_home