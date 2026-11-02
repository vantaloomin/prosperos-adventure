"""Record model calls (dungeon/model_calls.py): every model request and response, in full, only when turned on."""
import json

from dungeon import model_calls


def recorded(client) -> list[dict]:
    folder = model_calls.folder(client.app.state.database)
    return [json.loads(line) for path in sorted(folder.glob('*.jsonl')) for line in path.read_text().splitlines()]


def record(client, on=True) -> dict:
    response = client.put('/api/model-calls', json={'recording': on})
    assert response.status_code == 200, response.text
    return response.json()


def test_the_address_loses_its_query_string():
    assert model_calls.address('https://example.test/v1beta?key=abc') == 'https://example.test/v1beta'
