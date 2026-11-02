"""This PC's timezone as an IANA name, for a workspace that has not been given one.

The interface sends the browser's zone when it opens; this is the fallback the backend can work out on
its own, from the Windows registry (mapped with CLDR) or the TZ variable and /etc/localtime elsewhere.
"""
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dungeon.windows_zones import WINDOWS_ZONES

TIMEZONE_KEY = r'SYSTEM\CurrentControlSet\Control\TimeZoneInformation'


def valid(name: str | None) -> str | None:
    if not name:
        return None
    try:
        ZoneInfo(name)
    except (ValueError, KeyError, OSError):  # ZoneInfoNotFoundError is a KeyError.
        return None
    return name


def windows_zone() -> str | None:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, TIMEZONE_KEY) as key:
            name, _ = winreg.QueryValueEx(key, 'TimeZoneKeyName')
    except OSError:
        return None
    # Older Windows versions pad the value with NULs.
    return WINDOWS_ZONES.get(str(name).rstrip('\0').strip())


def posix_zone() -> str | None:
    variable = os.environ.get('TZ', '').lstrip(':')
    if valid(variable):
        return variable
    try:
        target = str(Path('/etc/localtime').resolve())
    except OSError:
        target = ''
    if 'zoneinfo/' in target:
        return target.split('zoneinfo/', 1)[1]
    try:
        return Path('/etc/timezone').read_text(encoding='utf-8').strip() or None
    except OSError:
        return None


def detect() -> str | None:
    """None when the zone cannot be worked out; callers then leave the setting as it is."""
    try:
        return valid(windows_zone() if os.name == 'nt' else posix_zone())
    except Exception:  # Detection is a convenience and must never stop the app from starting.
        return None
