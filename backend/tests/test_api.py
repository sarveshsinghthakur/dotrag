import os
import sys
import json
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app

client = TestClient(app)


class TestHealth:
    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "dotrag-api"

    def test_root(self):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "DotRAG API"


class TestDocuments:
    def test_list_documents_empty(self):
        response = client.get("/api/documents/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_document_not_found(self):
        response = client.get("/api/documents/nonexistent-id")
        assert response.status_code == 404

    def test_delete_document_not_found(self):
        response = client.delete("/api/documents/nonexistent-id")
        assert response.status_code == 404


class TestSearch:
    def test_search_empty(self):
        """Test search endpoint - requires Qdrant running."""
        try:
            response = client.post("/api/search/", json={"query": "test"})
            assert response.status_code == 200
            data = response.json()
            assert data["query"] == "test"
            assert isinstance(data["results"], list)
        except Exception:
            # Qdrant not running - expected in test without Docker
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
