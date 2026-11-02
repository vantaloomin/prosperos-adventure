"""Sunrise, sunset and the moon's phase, computed from a place's coordinates; no network.

Sun times use NOAA's solar equations (good to a minute or two away from the poles); the moon's
phase counts mean synodic months from a known new moon, so it can be off by up to a day.
"""
import math
from datetime import date, datetime, timedelta, timezone

SYNODIC_DAYS = 29.530588853
KNOWN_NEW_MOON = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
PHASES = ((1.0, 'new moon'), (6.4, 'waxing crescent'), (8.4, 'first quarter'), (13.8, 'waxing gibbous'),
          (15.8, 'full moon'), (21.1, 'waning gibbous'), (23.1, 'last quarter'), (28.5, 'waning crescent'),
          (30.0, 'new moon'))


def sun(day: date, lat: float, lon: float) -> tuple[datetime | None, datetime | None]:
    """Sunrise and sunset on this date in UTC; (None, None) when the sun does not rise or set that day."""
    noon = datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc) - timedelta(hours=lon / 15)
    century = ((noon - datetime(2000, 1, 1, 12, tzinfo=timezone.utc)).total_seconds() / 86400) / 36525
    mean_long = (280.46646 + century * (36000.76983 + century * 0.0003032)) % 360
    anomaly = math.radians(357.52911 + century * (35999.05029 - 0.0001537 * century))
    eccentricity = 0.016708634 - century * (0.000042037 + 0.0000001267 * century)
    centre = (math.sin(anomaly) * (1.914602 - century * (0.004817 + 0.000014 * century))
              + math.sin(2 * anomaly) * (0.019993 - 0.000101 * century) + math.sin(3 * anomaly) * 0.000289)
    omega = math.radians(125.04 - 1934.136 * century)
    apparent = math.radians(mean_long + centre - 0.00569 - 0.00478 * math.sin(omega))
    obliquity = math.radians(23 + (26 + (21.448 - century * (46.815 + century * (0.00059 - century * 0.001813)))
                                   / 60) / 60 + 0.00256 * math.cos(omega))
    declination = math.asin(math.sin(obliquity) * math.sin(apparent))
    y = math.tan(obliquity / 2) ** 2
    mean_long = math.radians(mean_long)
    equation = 4 * math.degrees(y * math.sin(2 * mean_long) - 2 * eccentricity * math.sin(anomaly)
                                + 4 * eccentricity * y * math.sin(anomaly) * math.cos(2 * mean_long)
                                - 0.5 * y * y * math.sin(4 * mean_long)
                                - 1.25 * eccentricity ** 2 * math.sin(2 * anomaly))
    latitude = math.radians(lat)
    cosine = (math.cos(math.radians(90.833)) / (math.cos(latitude) * math.cos(declination))
              - math.tan(latitude) * math.tan(declination))
    if not -1 <= cosine <= 1:
        return None, None
    hour_angle = math.degrees(math.acos(cosine))
    midnight = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    solar_noon = 720 - 4 * lon - equation
    return (midnight + timedelta(minutes=solar_noon - 4 * hour_angle),
            midnight + timedelta(minutes=solar_noon + 4 * hour_angle))


def moon(instant: datetime) -> str:
    """The moon's phase at this moment, by name."""
    age = ((instant - KNOWN_NEW_MOON).total_seconds() / 86400) % SYNODIC_DAYS
    return next(name for limit, name in PHASES if age < limit)
