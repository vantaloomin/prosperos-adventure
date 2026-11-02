"""Claude Code and Codex accounts found on this computer, so a profile can pick one (Settings > Models).

A CLI keeps each account's sign-in in a folder of its own: CLAUDE_CONFIG_DIR for Claude Code, CODEX_HOME for
Codex. People with two accounts usually make a second command for the second folder, such as `claude2`: a small
.cmd, .bat, .ps1 or shell script on PATH, a function or alias in their PowerShell profile, or an alias in a shell
start-up file. Those are read here as text, never run, for the folder they set. Folders in the home folder named
like the CLI's own (.claude-account2, .codex-work) that hold a sign-in are found too, in case the command is
defined some other way. The usual account (no folder) is listed whenever the CLI itself is on PATH.

A profile never runs the wrapper itself: it runs the CLI with the folder set, so Adventure's own flags and the
environment it strips (adventure/providers/claude_code.py, codex.py) stay exactly as they are. Whether each account
is signed in, and to which email for Claude, comes from the CLI's own status command; no sign-in file is read.
"""
import asyncio
import os
import re
import shutil
from pathlib import Path

from adventure.errors import DomainError
from adventure.providers import claude_code, codex

CLIS = {
    'claude_code': {'command': 'claude', 'variable': 'CLAUDE_CONFIG_DIR', 'folder': '.claude',
                    'markers': ('.credentials.json', '.claude.json')},
    'codex': {'command': 'codex', 'variable': 'CODEX_HOME', 'folder': '.codex', 'markers': ('auth.json', 'config.toml')},
}
SCRIPT_SUFFIXES = {'', '.cmd', '.bat', '.ps1', '.sh'}
SCRIPT_LIMIT = 65536


def cli_named(name: str) -> str | None:
    """The provider whose CLI a command or folder is named after (`claude2`, `claude-work`, `codex_alt`)."""
    for provider, cli in CLIS.items():
        if re.fullmatch(re.escape(cli['command']) + r'[\w.-]*', name, re.IGNORECASE):
            return provider
    return None


def environment_value(name: str) -> str | None:
    if name.upper() in {'HOME', 'USERPROFILE'}:
        return os.environ.get(name) or str(Path.home())
    return os.environ.get(name)


def expanded(value: str) -> str | None:
    """A folder as a script wrote it (%USERPROFILE%, $env:USERPROFILE, $HOME, ~), or None when it is not a full path
    once its variables are filled in."""
    value = value.strip().strip('"\'').strip()

    def filled(match: re.Match) -> str:
        found = environment_value(next(group for group in match.groups() if group))
        if found is None:
            raise KeyError(match[0])
        return found
    try:
        value = re.sub(r'%(\w+)%|\$\{env:(\w+)\}|\$env:(\w+)|\$\{(\w+)\}|\$(\w+)', filled, value, flags=re.IGNORECASE)
    except KeyError:
        return None
    value = os.path.expanduser(value).rstrip('\\/') or value
    return value if value and os.path.isabs(value) else None


def folder_in(text: str, variable: str) -> str | None:
    """The folder a script, function or alias sets `variable` to, in cmd, PowerShell or shell spelling."""
    name = re.escape(variable)
    patterns = (rf'(?im)\bset\s+"{name}=([^"\r\n]*)"',  # set "CLAUDE_CONFIG_DIR=C:\a b"
                rf'(?im)\bset\s+{name}=([^\r\n&|]*)',  # set CLAUDE_CONFIG_DIR=C:\a b
                # $env:X = "…", X=… claude, export X="…", [Environment]::SetEnvironmentVariable('X', '…')
                rf'(?i)\b{name}\b["\']?\s*[=,]\s*("[^"\r\n]*"|\'[^\'\r\n]*\'|[^\s"\';&|)]+)')
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            if folder := expanded(match[1]):
                return folder
    return None


def script_text(path: Path) -> str | None:
    try:
        if not path.is_file() or path.stat().st_size > SCRIPT_LIMIT:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    return None if b'\0' in data else data.decode('utf-8', 'replace')


def path_commands() -> list[dict]:
    """Wrapper scripts on PATH named after a CLI, other than the CLI itself, that set its account folder."""
    found, seen = [], set()
    for folder in dict.fromkeys(entry for entry in os.environ.get('PATH', '').split(os.pathsep) if entry):
        try:
            entries = list(Path(folder).iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.suffix.lower() not in SCRIPT_SUFFIXES:
                continue
            stem = entry.stem
            provider = cli_named(stem)
            if not provider or stem.lower() == CLIS[provider]['command'] or (provider, stem.lower()) in seen:
                continue
            text = script_text(entry)
            if text and (account := folder_in(text, CLIS[provider]['variable'])):
                seen.add((provider, stem.lower()))
                found.append({'provider': provider, 'name': stem, 'folder': account, 'source': str(entry)})
    return found


def profile_files() -> list[Path]:
    """PowerShell profiles (Windows PowerShell, PowerShell 7, OneDrive's Documents) and shell start-up files."""
    home = Path.home()
    documents = [home / 'Documents', *sorted(home.glob('OneDrive*/Documents')), *sorted(home.glob('OneDrive*/Dokumente'))]
    names = ('Microsoft.PowerShell_profile.ps1', 'profile.ps1', 'Microsoft.VSCode_profile.ps1')
    files = [place / shell / name for place in documents for shell in ('PowerShell', 'WindowsPowerShell') for name in names]
    files += [home / '.config' / 'powershell' / name for name in names]
    files += [home / name for name in ('.bashrc', '.bash_profile', '.bash_aliases', '.zshrc', '.profile')]
    return [file for file in dict.fromkeys(files) if file.is_file()]


def block_after(text: str, start: int) -> str:
    """The `{ … }` that opens at `start`, by counting braces."""
    depth = 0
    for index in range(start, len(text)):
        depth += {'{': 1, '}': -1}.get(text[index], 0)
        if depth == 0:
            return text[start:index + 1]
    return text[start:]


def definitions(text: str) -> dict[str, str]:
    """Each function and alias a profile defines, by name, with the text that makes it up."""
    found = {}
    for match in re.finditer(r'(?im)^[ \t]*(?:function[ \t]+(?:global:|script:)?([\w.-]+)[^{\r\n]*|([\w.-]+)[ \t]*\(\)[ \t]*)\{',
                             text):
        found.setdefault(match[1] or match[2], block_after(text, match.end() - 1))
    for match in re.finditer(r'(?im)^[ \t]*(?:Set|New)-Alias\b(.*)$', text):
        words = [word.strip('"\'') for word in re.findall(r'"[^"]*"|\'[^\']*\'|\S+', match[1])]
        plain = [word for word in words if not word.startswith('-')]
        if len(plain) >= 2:
            found.setdefault(plain[0], 'alias:' + plain[1])
    for match in re.finditer(r'(?im)^[ \t]*alias[ \t]+([\w.-]+)=("[^"\r\n]*"|\'[^\'\r\n]*\'|\S+)', text):
        found.setdefault(match[1], match[2])
    return found


def profile_commands() -> list[dict]:
    """Functions and aliases named after a CLI in the PowerShell profiles and shell start-up files."""
    found = []
    for file in profile_files():
        text = script_text(file)
        if not text:
            continue
        defined = definitions(text)
        for name, body in defined.items():
            provider = cli_named(name)
            if not provider or name.lower() == CLIS[provider]['command']:
                continue
            if body.startswith('alias:'):
                # Set-Alias claude2 Use-Claude2 points at a function; Set-Alias claude2 C:\…\claude2.ps1 at a script.
                target = body.removeprefix('alias:')
                body = defined.get(target) or script_text(Path(os.path.expandvars(target))) or ''
            if account := folder_in(body, CLIS[provider]['variable']):
                found.append({'provider': provider, 'name': name, 'folder': account, 'source': str(file)})
    return found


def home_folders() -> list[dict]:
    """Folders in the home folder named after a CLI's own (.claude-account2) that hold a sign-in or settings."""
    found = []
    try:
        entries = sorted(Path.home().iterdir())
    except OSError:
        return found
    for entry in entries:
        provider = cli_named(entry.name.removeprefix('.')) if entry.name.startswith('.') else None
        if (provider and entry.name.lower() != CLIS[provider]['folder'] and entry.is_dir()
                and any((entry / marker).is_file() for marker in CLIS[provider]['markers'])):
            found.append({'provider': provider, 'name': '', 'folder': str(entry), 'source': str(entry)})
    return found


def same_folder(folder: str) -> str:
    return os.path.normcase(os.path.normpath(folder))


def default_folder(provider: str) -> str:
    return same_folder(str(Path.home() / CLIS[provider]['folder']))


def found_accounts() -> list[dict]:
    """Every account on this computer, one per provider and folder: the usual one first, then the rest by name.
    `account_dir` is what a profile's cli_account_dir takes ('' for the usual account)."""
    accounts: dict[tuple[str, str], dict] = {}
    for provider, cli in CLIS.items():
        if shutil.which(cli['command']):
            accounts[(provider, '')] = {'provider': provider, 'account_dir': '', 'commands': [cli['command']],
                                        'sources': []}
    for item in path_commands() + profile_commands() + home_folders():
        folder = same_folder(item['folder'])
        usual = folder == default_folder(item['provider'])
        account = accounts.setdefault((item['provider'], '' if usual else folder), {
            'provider': item['provider'], 'account_dir': '' if usual else item['folder'], 'commands': [], 'sources': []})
        if item['name'] and item['name'] not in account['commands']:
            account['commands'].append(item['name'])
        if item['source'] not in account['sources']:
            account['sources'].append(item['source'])
    return sorted(accounts.values(), key=lambda account: (list(CLIS).index(account['provider']), bool(account['account_dir']),
                                                          (account['commands'] or [account['account_dir']])[0].lower()))


async def signed_in(account: dict) -> dict:
    """Whether the account is signed in (and, for Claude, as whom), from the CLI's own status command."""
    config = {'cli_account_dir': account['account_dir']}
    try:
        if account['provider'] == 'claude_code':
            state = await claude_code.login_state(claude_code.executable_path(config), config)
            return {**account, 'signed_in': True, 'email': state['email']}
        await codex.login_state(codex.executable_path(config), config)
        return {**account, 'signed_in': True, 'email': ''}
    except (DomainError, OSError, NotImplementedError, TimeoutError):
        return {**account, 'signed_in': False, 'email': ''}


async def accounts_with_logins() -> list[dict]:
    accounts = await asyncio.to_thread(found_accounts)
    return list(await asyncio.gather(*(signed_in(account) for account in accounts)))
