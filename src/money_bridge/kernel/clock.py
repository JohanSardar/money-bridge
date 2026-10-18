import os
import time
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from money_bridge.kernel.errors import ErrorCode, MoneyBridgeError

PROFILE_ENV = "MONEYBRIDGE_PROFILE"
TEST_CLOCK_ENV = "MONEYBRIDGE_TEST_CLOCK_FILE"


class Profile(StrEnum):
    PRODUCTION = "production"
    TEST = "test"


def current_profile() -> Profile:
    raw = os.environ.get(PROFILE_ENV, Profile.PRODUCTION.value)
    try:
        return Profile(raw)
    except ValueError as error:
        raise MoneyBridgeError(ErrorCode.INVALID_REQUEST, f"unknown profile: {raw}") from error


def require_test_profile(feature: str) -> None:
    if current_profile() is not Profile.TEST:
        raise MoneyBridgeError(ErrorCode.INVALID_REQUEST, f"{feature} is only available in the test profile")


class Clock(Protocol):
    def now(self) -> datetime: ...

    def monotonic(self) -> float: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return time.monotonic()


class OffsetFileClock:
    def __init__(self, path: Path) -> None:
        require_test_profile("the controllable clock")
        self._path = path

    def _offset(self) -> timedelta:
        try:
            text = self._path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return timedelta(0)
        return timedelta(seconds=float(text)) if text else timedelta(0)

    def now(self) -> datetime:
        return datetime.now(UTC) + self._offset()

    def monotonic(self) -> float:
        return time.monotonic() + self._offset().total_seconds()


def clock_for_environment() -> Clock:
    path = os.environ.get(TEST_CLOCK_ENV)
    if path:
        return OffsetFileClock(Path(path))
    return SystemClock()


def to_iso(moment: datetime) -> str:
    if moment.tzinfo is None:
        raise MoneyBridgeError(ErrorCode.INTERNAL, "naive datetimes are not allowed")
    return moment.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def from_iso(text: str) -> datetime:
    moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        raise MoneyBridgeError(ErrorCode.INVALID_REQUEST, f"timestamp needs a timezone: {text}")
    return moment.astimezone(UTC)
