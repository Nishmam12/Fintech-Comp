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


def _sever_idle_connection(pool) -> None:
    """Cut the pool's idle connection underneath psycopg, as the hosted pooler does to idle clients."""
    import socket
    idle = list(pool._pool)[0]
    sock = socket.socket(fileno=idle.pgconn.socket)
    sock.shutdown(socket.SHUT_RDWR)
    sock.detach()                       # leave the descriptor to psycopg; only the connection is severed


def test_pool_replaces_a_connection_the_server_dropped(settings):
    """K1: the hosted pooler drops idle connections. A pool without a connection check hands the dead one
    to the next request (a 500); ours must discard it and serve a working one."""
    from budget_kernel.db.connection import make_pool

    pool = make_pool(settings, "public", max_size=2)
    try:
        with pool.connection() as c:
            c.execute("select 1")
        _sever_idle_connection(pool)
        with pool.connection() as c:
            assert c.execute("select 1 as ok").fetchone()["ok"] == 1
    finally:
        pool.close()


def test_the_severing_helper_really_breaks_an_unchecked_pool(settings):
    """Guards the test above: without the check the same severed connection fails."""
    import psycopg
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    pool = ConnectionPool(settings.database_url, min_size=1, max_size=2, kwargs={"row_factory": dict_row}, open=True)
    try:
        with pool.connection() as c:
            c.execute("select 1")
        _sever_idle_connection(pool)
        with pytest.raises(psycopg.OperationalError):
            with pool.connection() as c:
                c.execute("select 1")
    finally:
        pool.close()
