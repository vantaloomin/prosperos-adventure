import asyncio

import httpx
import pytest

from adventure import updates


@pytest.fixture(autouse=True)
def fresh():
    updates._last.clear()
    yield
    updates._last.clear()


def release(tag: str, **extra) -> dict:
    return {'tag_name': tag, 'name': f'{tag}: Characters Who Think', 'prerelease': True, 'draft': False,
            'html_url': f'https://github.com/{updates.REPOSITORY}/releases/tag/{tag}',
            'published_at': '2026-11-03T13:30:00Z', **extra}


def answering(*releases, calls: list | None = None, status: int = 200):
    def handler(request: httpx.Request):
        if calls is not None:
            calls.append(request.url)
        return httpx.Response(status, json=list(releases))
    return httpx.MockTransport(handler)


def test_versions_compare_by_number():
    assert updates.newer('v1.1.10', '1.1.9')
    assert updates.newer('v1.2', '1.1.5')
    assert not updates.newer('v1.1.5', '1.1.5')
    assert not updates.newer('v1.1.5.0', '1.1.5')
    assert not updates.newer('v1.1.4', '1.1.5')
    assert not updates.newer('nightly', '1.1.5')


def test_a_newer_pre_release_is_offered_with_its_page(monkeypatch):
    monkeypatch.setattr(updates, 'VERSION', '0.1.0')
    found = asyncio.run(updates.check(answering(release('v0.1.0'), release('v0.2.0')), now=0))
    assert found['status'] == 'newer'
    assert found['latest'] == '0.2.0' and found['current'] == '0.1.0'
    assert found['page'].endswith('/releases/tag/v0.2.0')
    assert found['install'] in {'installer', 'folder'}


def test_drafts_and_odd_tags_are_passed_over(monkeypatch):
    monkeypatch.setattr(updates, 'VERSION', '0.1.0')
    found = asyncio.run(updates.check(answering(release('v0.3.0', draft=True), release('nightly'), release('v0.1.0')), now=0))
    assert found['status'] == 'current' and found['latest'] == '0.1.0'


def test_the_same_release_is_up_to_date(monkeypatch):
    monkeypatch.setattr(updates, 'VERSION', '0.1.0')
    assert asyncio.run(updates.check(answering(release('v0.1.0')), now=0))['status'] == 'current'


def test_no_release_yet_is_unavailable():
    found = asyncio.run(updates.check(answering(), now=0))
    assert found['status'] == 'unavailable' and found['page'] == updates.RELEASES_PAGE


def test_a_repeat_press_reuses_the_answer_for_a_while():
    calls = []
    asyncio.run(updates.check(answering(release('v9.0.0'), calls=calls), now=0))
    asyncio.run(updates.check(answering(release('v9.0.0'), calls=calls), now=60))
    assert len(calls) == 1
    asyncio.run(updates.check(answering(release('v9.0.0'), calls=calls), now=updates.REUSE_SECONDS + 1))
    assert len(calls) == 2


def test_a_failed_lookup_says_so_and_is_not_kept():
    calls = []
    found = asyncio.run(updates.check(answering(release('v9.0.0'), calls=calls, status=403), now=0))
    assert found['status'] == 'unavailable' and found['latest'] is None
    assert found['page'] == updates.RELEASES_PAGE
    asyncio.run(updates.check(answering(release('v9.0.0'), calls=calls), now=1))
    assert len(calls) == 2


def test_the_installer_copy_is_told_apart(tmp_path, monkeypatch):
    monkeypatch.setattr(updates, 'APP_FOLDER', tmp_path)
    assert updates.install_kind() == 'folder'
    (tmp_path / updates.BUNDLE_MANIFEST).write_text('{}')
    assert updates.install_kind() == 'installer'


def test_the_route_answers_without_reaching_github(client, monkeypatch):
    real = updates.fetch_latest
    monkeypatch.setattr(updates, 'fetch_latest', lambda transport=None: real(answering(release('v99.0.0'))))
    found = client.post('/api/updates/check').json()
    assert found['status'] == 'newer' and found['latest'] == '99.0.0'
