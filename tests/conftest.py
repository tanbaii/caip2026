"""Shared test fixtures.

Sets DB_PATH to a temporary file BEFORE any test module imports app.main,
so the production database is never touched.
"""

import os
import tempfile

# Must run before app.main is imported (module-level storage init).
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["DB_PATH"] = _tmp_db.name

import pytest  # noqa: E402


@pytest.fixture(autouse=True, scope="session")
def _cleanup_temp_db():
    yield
    try:
        os.unlink(_tmp_db.name)
    except OSError:
        pass


@pytest.fixture(autouse=True)
def _reset_db():
    """Re-initialise an empty database before every test so tests are isolated."""
    from app.main import storage

    for table in ("users", "user_state", "reports"):
        with storage._connect() as conn:
            conn.execute(f"DELETE FROM {table}")
            conn.commit()
    storage._init_schema()
    yield
