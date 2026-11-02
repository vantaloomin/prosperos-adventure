"""Debug time: jump ahead or speed up the app clock to check several days quickly, then go back."""
import time


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


# A three-day jump takes about 15 s here and over a minute on a busy Windows runner, so the wait is by the clock.
SETTLE_SECONDS = 180


def settle(client):
    """Wait for a jump's walk to finish on the app's event loop."""
    deadline = time.monotonic() + SETTLE_SECONDS
    while time.monotonic() < deadline:
        status = ok(client.get('/api/debug-time'))
        if status['jumping'] is None:
            return status
        time.sleep(0.05)
    raise AssertionError('The jump did not finish.')


def count(client, table) -> int:
    with client.app.state.database.connect() as connection:
        return connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]  # noqa: S608


