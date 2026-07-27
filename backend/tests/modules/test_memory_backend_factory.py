"""Tests for memory backend factory and MEMORY_BACKEND config validation."""

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.core.config import AISettings


def test_unknown_memory_backend_rejected_by_settings():
    """Unknown MEMORY_BACKEND value must fail at settings validation."""
    with pytest.raises(ValidationError, match="MEMORY_BACKEND"):
        AISettings(**{"MEMORY_BACKEND": "neo4j"})


def test_valid_memory_backend_pgvector():
    s = AISettings(**{"MEMORY_BACKEND": "pgvector"})
    assert s.memory_backend == "pgvector"


def test_valid_memory_backend_graphiti():
    s = AISettings(**{"MEMORY_BACKEND": "graphiti"})
    assert s.memory_backend == "graphiti"


def test_create_backend_unknown_raises():
    """_create_backend must raise ValueError for unknown backend type."""
    from app.modules.memory.services.memory_service import _create_backend

    with patch("app.modules.memory.services.memory_service.settings") as mock_settings:
        mock_settings.ai.memory_backend = "unknown"
        with pytest.raises(ValueError, match="Unknown MEMORY_BACKEND"):
            _create_backend(AsyncMock())


def test_create_backend_pgvector():
    """_create_backend returns PgVectorMemoryBackend for pgvector."""
    from app.modules.memory.backends.pgvector import PgVectorMemoryBackend
    from app.modules.memory.services.memory_service import _create_backend

    with patch("app.modules.memory.services.memory_service.settings") as mock_settings:
        mock_settings.ai.memory_backend = "pgvector"
        backend = _create_backend(AsyncMock())
        assert isinstance(backend, PgVectorMemoryBackend)
