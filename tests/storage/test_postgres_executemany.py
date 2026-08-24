"""Postgres adapter must translate qmark placeholders for batch writes."""

from src.storage.database import _PostgresConnection


def test_postgresql_executemany_translates_qmark_parameters():
    class FakeCursor:
        def __init__(self):
            self.call = None

        def executemany(self, sql, params):
            self.call = (sql, params)
            return "cursor"

    class FakeConnection:
        def __init__(self):
            self.cursor_obj = FakeCursor()

        def cursor(self):
            return self.cursor_obj

    raw = FakeConnection()
    result = _PostgresConnection(raw).executemany(
        "INSERT INTO alert_jobs (job_type, payload_json) VALUES (?, ?)",
        [("deliver", "{}"), ("deliver", "{}")],
    )
    assert result == "cursor"
    assert raw.cursor_obj.call == (
        "INSERT INTO alert_jobs (job_type, payload_json) VALUES (%s, %s)",
        [("deliver", "{}"), ("deliver", "{}")],
    )
