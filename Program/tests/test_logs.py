import logging
import logging.config

from dungeon import logs


def test_credentials_are_masked():
    line = ('Authorization: Bearer abc.def-ghi api_key=XYZ123456 "token": "t0k3n" '
            'sk-proj-ABCDEFGH12345678 hf_ABCDEFGHIJKL normal words stay')
    masked = logs.redact(line)
    for secret in ('abc.def-ghi', 'XYZ123456', 't0k3n', 'sk-proj-ABCDEFGH12345678', 'hf_ABCDEFGHIJKL'):
        assert secret not in masked
    assert 'normal words stay' in masked


def test_log_file_masks_messages_and_tracebacks(tmp_path):
    logging.config.dictConfig(logs.config(tmp_path))
    logger = logging.getLogger('uvicorn.error')
    logger.info('Connecting with %s', 'Bearer sk-live-SECRETSECRET')
    try:
        raise RuntimeError('provider refused api_key=SECRETVALUE')
    except RuntimeError:
        logger.exception('Request failed')
    for handler in logger.handlers:
        handler.flush()
    text = (tmp_path / 'logs' / 'dungeon.log').read_text(encoding='utf-8')
    assert 'Request failed' in text and 'RuntimeError' in text
    assert 'SECRET' not in text
    for name in ('uvicorn', 'uvicorn.error', 'dungeon'):
        configured = logging.getLogger(name)
        for handler in list(configured.handlers):
            handler.close()
            configured.removeHandler(handler)
        configured.propagate = True


def test_unexpected_failures_say_what_failed_and_why_in_plain_words():
    """Testers saw only "Something went wrong in the Dungeon. Please try again" and could not tell what broke."""
    import sqlite3

    from dungeon import troubleshoot
    said = troubleshoot.for_request('GET', '/api/world', ValueError('jpl names careers this city does not offer'), '/x/dungeon.log')
    assert said.startswith("Couldn't load the cities. This looks like a bug")
    assert said.endswith('Details: ValueError: jpl names careers this city does not offer')
    assert '/x/dungeon.log' in said and 'Traceback' not in said
    assert troubleshoot.area('/api/story/messages') == 'the story' and troubleshoot.area('/api/storyline') == 'the Dungeon'
    locked = troubleshoot.for_request('POST', '/api/story/messages', sqlite3.OperationalError('database is locked'))
    assert locked.startswith("Couldn't finish that in the story. Its data file was busy")
    assert 'read-only' in troubleshoot.reason(sqlite3.OperationalError('attempt to write a readonly database'))
    assert troubleshoot.reason(KeyError('x')) is None
    assert len(troubleshoot.detail(ValueError('x' * 1000))) == troubleshoot.DETAIL_LIMIT
