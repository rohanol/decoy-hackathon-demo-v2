import pytest
from fastapi.testclient import TestClient

from backend.main import create_app


@pytest.fixture
def client(tmp_path):
    """Fresh backend on its own temporary database file."""
    with TestClient(create_app(str(tmp_path / "test.db"))) as c:
        yield c
