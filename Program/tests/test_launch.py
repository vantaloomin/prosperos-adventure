import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from dungeon import launch
from dungeon.identity import APP_ID


def health_server(body):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            payload = json.dumps(body).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = HTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f'http://127.0.0.1:{server.server_address[1]}/'


def test_probe_recognizes_only_the_companion():
    ours, url = health_server({'app_id': APP_ID, 'version': '0.1.0'})
    study, other = health_server({'application': 'Roleplay', 'status': 'ok'})
    try:
        assert launch.probe(url) == 'ready'
        assert launch.probe(other) == 'foreign'
    finally:
        ours.shutdown()
        study.shutdown()


def test_reuse_never_claims_another_program(capsys):
    study, url = health_server({'application': 'Roleplay', 'status': 'ok'})
    try:
        assert launch.reuse(url, no_browser=True, wait=1) == 1
        assert 'used by another program' in capsys.readouterr().out
    finally:
        study.shutdown()


def test_reuse_opens_a_running_companion(capsys):
    ours, url = health_server({'app_id': APP_ID})
    try:
        assert launch.reuse(url, no_browser=True, wait=1) == 0
        assert 'already running' in capsys.readouterr().out
    finally:
        ours.shutdown()


def test_a_taken_port_cannot_be_reserved():
    first = launch.reserve_port(0)
    port = first.getsockname()[1]
    try:
        assert launch.reserve_port(port) is None
    finally:
        first.close()
