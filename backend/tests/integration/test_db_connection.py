import pytest

from budget_kernel.config import Settings
from budget_kernel.db.connection import transaction


@pytest.fixture(scope="module")
def settings():
    return Settings.load()


def test_connects_to_pooler(settings):
    with transaction(settings, schema="public") as conn:
        row = conn.execute("select current_database() as db, current_setting('server_version_num')::int as v").fetchone()
    assert row["db"] == "postgres"
    assert row["v"] >= 150000


def test_row_lock_available(settings):
    # The kernel serializes per mandate with SELECT ... FOR UPDATE; prove it works through this pooler.
    with transaction(settings, schema="public") as conn:
        conn.execute("create temp table lock_probe(id int primary key)")
        conn.execute("insert into lock_probe values (1)")
        assert conn.execute("select id from lock_probe where id=1 for update").fetchone()["id"] == 1
