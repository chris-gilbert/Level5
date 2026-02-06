import pytest

from level5.proxy import database

# Use in-memory test database
TEST_DB_PATH = ":memory:"


@pytest.fixture(autouse=True)
def _isolate_db(monkeypatch, tmp_path):
    """Use a temporary database for each test."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DB_PATH", db_path)
    database.init_db()
