import hashlib
import json
import unicodedata
from base64 import b32encode
from datetime import date, datetime
from decimal import Decimal

from money_bridge.kernel.errors import ErrorCode, MoneyBridgeError

JsonValue = None | bool | int | str | list["JsonValue"] | dict[str, "JsonValue"]


def _normalize(value: object) -> JsonValue:
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        raise MoneyBridgeError(ErrorCode.INVALID_REQUEST, "floats are not allowed in canonical data")
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, dict):
        normalized: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise MoneyBridgeError(ErrorCode.INVALID_REQUEST, "canonical object keys must be strings")
            normalized[unicodedata.normalize("NFC", key)] = _normalize(item)
        return normalized
    if isinstance(value, list | tuple):
        return [_normalize(item) for item in value]
    raise MoneyBridgeError(ErrorCode.INVALID_REQUEST, f"unsupported canonical type: {type(value).__name__}")


def canonical_json(value: object) -> bytes:
    return json.dumps(_normalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, item in pairs:
        if key in result:
            raise MoneyBridgeError(ErrorCode.INVALID_REQUEST, f"duplicate key: {key}")
        result[key] = item
    return result


def _reject_float(text: str) -> object:
    raise MoneyBridgeError(ErrorCode.INVALID_REQUEST, f"floats are not allowed: {text}")


def parse_strict_json(data: bytes | str) -> object:
    return json.loads(data, object_pairs_hook=_reject_duplicates, parse_float=_reject_float)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(value: object) -> str:
    return sha256_hex(canonical_json(value))


def stable_id(prefix: str, *parts: str) -> str:
    material = "\x1f".join(unicodedata.normalize("NFC", part) for part in parts).encode("utf-8")
    encoded = b32encode(hashlib.sha256(material).digest()).decode("ascii").lower().rstrip("=")
    return f"{prefix}_{encoded[:26]}"
