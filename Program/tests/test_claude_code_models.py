"""The Claude Code provider against a stand-in `claude` CLI: the real CLI and a real Claude login are not used."""
import asyncio
import json
import sys
import textwrap

import pytest

from dungeon.errors import DomainError
from dungeon.providers import claude_code
from dungeon.providers.config import ProfileConfig

# Prints the stream a `claude -p --output-format stream-json --include-partial-messages` turn writes, and
# records what it was given in seen.json beside itself.
STAND_IN = '''
import json, os, sys
from pathlib import Path
arguments = sys.argv[1:]
if arguments == ["--help"]:
    print(os.environ.get("STAND_IN_HELP", "  --safe-mode   Start with all customizations disabled"))
    sys.exit(0)
if arguments[:2] == ["auth", "status"]:
    state = os.environ.get("STAND_IN_LOGIN", "in")
    print(json.dumps({"loggedIn": state != "out", "authMethod": "api_key" if state == "key" else "claude.ai",
                      "email": os.environ.get("CLAUDE_CONFIG_DIR", "").endswith("second") and "two@example.com" or ""}))
    sys.exit(1 if state == "out" else 0)
system = Path(arguments[arguments.index("--system-prompt-file") + 1]).read_text(encoding="utf-8")
seen = {"arguments": arguments, "system": system, "stdin": sys.stdin.read(), "cwd": os.getcwd(),
        "api_key": os.environ.get("ANTHROPIC_API_KEY"),
        "environment": {name: value for name, value in os.environ.items() if "CLAUDE" in name}}
Path(__file__).with_name("seen.json").write_text(json.dumps(seen))
mode = os.environ.get("STAND_IN_MODE", "stream")
print(json.dumps({"type": "system", "subtype": "init"}))
if mode == "login":
    print(json.dumps({"type": "result", "subtype": "success", "is_error": True,
                      "result": "Not logged in. Please run /login"}))
    sys.exit(1)
if mode == "stream":
    for piece in ("Hello ", "there."):
        print(json.dumps({"type": "stream_event", "event": {"type": "content_block_delta",
                                                            "delta": {"type": "text_delta", "text": piece}}}))
    print(json.dumps({"type": "stream_event", "event": {"type": "content_block_delta",
                                                        "delta": {"type": "thinking_delta", "thinking": "hm"}}}))
print("")
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "Hello there.",
                  "usage": {"input_tokens": 12, "output_tokens": 3}}))
'''


@pytest.fixture
def stand_in(tmp_path, monkeypatch):
    script = tmp_path / 'claude_stand_in.py'
    script.write_text(textwrap.dedent(STAND_IN), encoding='utf-8')
    original = asyncio.create_subprocess_exec

    async def run(executable, *arguments, **options):
        return await original(executable, str(script), *arguments, **options)
    monkeypatch.setattr(claude_code, 'executable_path', lambda _config: sys.executable)
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', run)
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-not-for-the-cli')
    monkeypatch.setattr(claude_code, '_help_texts', {})
    return tmp_path


def config(**changes):
    return {'provider': 'claude_code', 'model': 'sonnet', 'timeout_seconds': 30, **changes}


def reply(**changes):
    async def collect():
        return [chunk async for chunk in claude_code.ClaudeCodeProvider().stream(
            config(**changes), None, 'You are Sally.', [{'role': 'user', 'content': 'Hi'},
                                                        {'role': 'assistant', 'content': 'Hey!'},
                                                        {'role': 'user', 'content': 'How are you?'}])]
    return asyncio.run(collect())


def test_a_reply_streams_from_claude_p_with_tools_off_and_the_plan_login(stand_in):
    chunks = reply(reasoning_effort='low')
    assert ''.join(chunk.text for chunk in chunks) == 'Hello there.'
    assert chunks[-1].done and chunks[-1].usage == {'input_tokens': 12, 'output_tokens': 3}
    seen = json.loads((stand_in / 'seen.json').read_text())
    arguments = seen['arguments']
    assert arguments[0] == '-p' and '--bare' not in arguments
    assert arguments[arguments.index('--tools') + 1] == ''
    assert arguments[arguments.index('--model') + 1] == 'sonnet'
    assert arguments[arguments.index('--effort') + 1] == 'low'
    assert {'--strict-mcp-config', '--disable-slash-commands', '--no-session-persistence'} <= set(arguments)
    assert seen['system'] == 'You are Sally.'
    assert seen['stdin'] == 'User: Hi\n\nAssistant: Hey!\n\nUser: How are you?\n\nAssistant:'
    assert 'dungeon-claude-' in seen['cwd']
    assert seen['api_key'] is None  # a key set for the Anthropic provider never replaces the plan


def test_only_dungeons_prompt_reaches_the_model(stand_in, monkeypatch):
    """The harness's own context is off: settings files, MCP servers, CLAUDE.md, memory and a parent session."""
    monkeypatch.setenv('CLAUDECODE', '1')
    monkeypatch.setenv('CLAUDE_CODE_SESSION_ID', 'parent-session')
    monkeypatch.setenv('CLAUDE_CODE_OAUTH_TOKEN', 'the-users-own-token')
    monkeypatch.setenv('CLAUDE_CODE_USE_BEDROCK', '1')
    reply()
    seen = json.loads((stand_in / 'seen.json').read_text())
    arguments = seen['arguments']
    assert arguments[arguments.index('--setting-sources') + 1] == ''
    assert json.loads(arguments[arguments.index('--mcp-config') + 1]) == {'mcpServers': {}}
    assert arguments[arguments.index('--max-turns') + 1] == '1'
    assert '--safe-mode' in arguments and '--permission-prompts' not in arguments  # only what --help lists
    assert '--append-system-prompt' not in arguments and '--bare' not in arguments
    environment = seen['environment']
    assert {name: environment[name] for name in claude_code.QUIET_ENV} == claude_code.QUIET_ENV
    assert 'CLAUDECODE' not in environment and 'CLAUDE_CODE_SESSION_ID' not in environment
    assert environment['CLAUDE_CODE_OAUTH_TOKEN'] == 'the-users-own-token'
    assert environment['CLAUDE_CODE_USE_BEDROCK'] == '1'


def test_an_older_cli_gets_no_flags_it_does_not_list(stand_in, monkeypatch):
    monkeypatch.setenv('STAND_IN_HELP', '  --tools <tools...>   Specify the list of available tools')
    reply()
    arguments = json.loads((stand_in / 'seen.json').read_text())['arguments']
    assert '--safe-mode' not in arguments and '--permission-prompts' not in arguments


def test_a_cli_that_does_not_stream_still_gives_the_whole_reply(stand_in, monkeypatch):
    monkeypatch.setenv('STAND_IN_MODE', 'whole')
    chunks = reply()
    assert [chunk.text for chunk in chunks] == ['Hello there.'] and chunks[0].done


def test_a_missing_login_says_how_to_sign_in(stand_in, monkeypatch):
    monkeypatch.setenv('STAND_IN_MODE', 'login')
    with pytest.raises(DomainError) as raised:
        reply()
    assert raised.value.message == claude_code.LOGIN_STEP


def test_test_connection_checks_the_login_and_lists_the_model_names(stand_in, monkeypatch):
    provider = claude_code.ClaudeCodeProvider()
    result = asyncio.run(provider.check(config(), None))
    assert result['models'] == ['sonnet', 'opus', 'haiku', 'fable'] and result['location'] == sys.executable
    assert result['model_details'][0]['supported_efforts'] == list(claude_code.EFFORTS)
    assert 'signed in' in result['note'] and 'API key' not in result['note']
    monkeypatch.setenv('STAND_IN_LOGIN', 'key')
    assert 'billed to that key' in asyncio.run(provider.check(config(), None))['note']
    monkeypatch.setenv('STAND_IN_LOGIN', 'out')
    with pytest.raises(DomainError) as raised:
        asyncio.run(provider.check(config(), None))
    assert raised.value.message == claude_code.LOGIN_STEP


def test_the_profile_takes_a_full_cli_location_and_plan_efforts_only():
    profile = ProfileConfig(provider='claude_code', model='opus', reasoning_effort='max',
                            cli_path=sys.executable)
    assert profile.base_url == '' and profile.cli_path == sys.executable
    for bad in ({'cli_path': 'claude'}, {'reasoning_effort': 'minimal'}, {'temperature': 0.5}):
        with pytest.raises(ValueError):
            ProfileConfig(provider='claude_code', model='opus', **bad)
    with pytest.raises(ValueError):
        ProfileConfig(provider='codex', model='gpt-5.5', cli_path=sys.executable)


def test_a_cli_location_that_does_not_exist_is_reported(tmp_path):
    with pytest.raises(DomainError) as raised:
        claude_code.executable_path({'cli_path': str(tmp_path / 'missing' / 'claude')})
    assert 'location set in this profile' in raised.value.message


def test_a_profile_can_use_its_own_claude_account(stand_in, monkeypatch, tmp_path):
    """Two Claude accounts, two profiles: each profile's folder keeps its own sign-in, and a token from the
    environment never stands in for it."""
    monkeypatch.setenv('CLAUDE_CODE_OAUTH_TOKEN', 'the-usual-accounts-token')
    folder = str(tmp_path / 'second')
    reply(cli_account_dir=folder)
    environment = json.loads((stand_in / 'seen.json').read_text())['environment']
    assert environment['CLAUDE_CONFIG_DIR'] == folder and 'CLAUDE_CODE_OAUTH_TOKEN' not in environment
    reply()
    assert 'CLAUDE_CONFIG_DIR' not in json.loads((stand_in / 'seen.json').read_text())['environment']
    provider = claude_code.ClaudeCodeProvider()
    assert 'signed in as two@example.com' in asyncio.run(provider.check(config(cli_account_dir=folder), None))['note']
    monkeypatch.setenv('STAND_IN_LOGIN', 'out')
    with pytest.raises(DomainError) as raised:
        asyncio.run(provider.check(config(cli_account_dir=folder), None))
    assert folder in raised.value.message and 'CLAUDE_CONFIG_DIR' in raised.value.message


def test_each_account_has_its_own_places_and_the_folder_must_be_a_full_path():
    from dungeon.providers.scheduling import resource_for
    assert resource_for(config()) == ('claude-cli', 2)
    assert resource_for(config(cli_account_dir='/home/me/.claude-second')) == ('claude-cli:/home/me/.claude-second', 2)
    assert ProfileConfig(provider='claude_code', model='sonnet', cli_account_dir=sys.prefix).cli_account_dir == sys.prefix
    for provider, folder in (('claude_code', 'claude-second'), ('codex', sys.prefix)):
        with pytest.raises(ValueError):
            ProfileConfig(provider=provider, model='sonnet', cli_account_dir=folder)


def test_a_json_schema_goes_to_a_cli_that_lists_the_flag_and_the_structured_answer_comes_back():
    shape = {'type': 'object'}
    arguments = claude_code.claude_arguments('claude', {'model': 'sonnet', 'json_schema': shape}, 'system.txt',
                                             '--json-schema <schema>')
    assert arguments[arguments.index('--json-schema') + 1] == json.dumps(shape)
    assert '--json-schema' not in claude_code.claude_arguments('claude', {'model': 'sonnet', 'json_schema': shape},
                                                               'system.txt', '')
    chunk = claude_code.claude_event({'type': 'result', 'subtype': 'success', 'result': '',
                                      'structured_output': {'facts': []}})
    assert json.loads(chunk.text) == {'facts': []}
