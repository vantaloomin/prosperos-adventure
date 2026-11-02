"""Real instants are stored in UTC; tests substitute a controllable clock."""
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dungeon.errors import DomainError


class Clock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock(Clock):
    def __init__(self, instant: datetime):
        self.instant = instant

    def now(self) -> datetime:
        return self.instant

    def advance(self, delta):
        self.instant += delta


class AppClock(Clock):
    """The clock the whole app reads (Database.clock). It is real time unless debug time (dungeon/debug_time.py)
    has moved it ahead or set it running faster: then now = where it was moved to + real time since, times speed."""

    def __init__(self, base: Clock | None = None):
        self.base = base or Clock()
        self.anchor_real: datetime | None = None
        self.anchor_app: datetime | None = None
        self.speed = 1.0

    @property
    def shifted(self) -> bool:
        return self.anchor_app is not None

    def real(self) -> datetime:
        return self.base.now()

    def now(self) -> datetime:
        if self.anchor_app is None:
            return self.base.now()
        return self.anchor_app + (self.base.now() - self.anchor_real) * self.speed

    def shift(self, instant: datetime, speed: float | None = None):
        """From this real moment on, the app's time is `instant`, running at `speed` (unchanged when None)."""
        self.anchor_real, self.anchor_app = self.base.now(), instant
        if speed is not None:
            self.speed = float(speed)

    def reset(self):
        self.anchor_real = self.anchor_app = None
        self.speed = 1.0

    def wait(self, seconds: float) -> float:
        """Real seconds to sleep so a loop meant to run every `seconds` of app time keeps up with a fast clock."""
        return max(1.0, seconds / self.speed) if self.speed > 1 else seconds


def stamp(instant: datetime) -> str:
    return instant.astimezone(UTC).isoformat(timespec='microseconds')


def parse(value: str | None) -> datetime | None:
    if value is None:
        return None
    instant = datetime.fromisoformat(value)
    if instant.tzinfo is None:
        raise DomainError('Times must include a UTC offset.', 422)
    return instant.astimezone(UTC)


def zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise DomainError(f'Unknown timezone: {name}.', 422) from error
