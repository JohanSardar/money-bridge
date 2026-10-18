from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from money_bridge.kernel import MoneyBridgeError, canonical_json, digest, parse_strict_json, stable_id

json_values = st.recursive(
    st.none() | st.booleans() | st.integers() | st.text() | st.decimals(allow_nan=False, allow_infinity=False),
    lambda children: st.lists(children) | st.dictionaries(st.text(), children),
    max_leaves=20,
)


@given(json_values)
def test_canonical_json_is_stable_under_round_trip(value: object) -> None:
    encoded = canonical_json(value)
    assert canonical_json(parse_strict_json(encoded)) == encoded


def test_key_order_and_unicode_form_do_not_change_digest() -> None:
    assert digest({"b": "é", "a": 1}) == digest({"a": 1, "b": "é"})


def test_floats_rejected_everywhere() -> None:
    with pytest.raises(MoneyBridgeError):
        canonical_json({"amount": 1.5})
    with pytest.raises(MoneyBridgeError):
        parse_strict_json('{"amount": 1.5}')


def test_duplicate_keys_rejected() -> None:
    with pytest.raises(MoneyBridgeError):
        parse_strict_json('{"a": 1, "a": 2}')


def test_decimal_keeps_scale() -> None:
    assert canonical_json({"amount": Decimal("12.50")}) == b'{"amount":"12.50"}'


def test_stable_id_is_deterministic_and_prefixed() -> None:
    first = stable_id("txn", "con_a", "acct", "t1")
    assert first == stable_id("txn", "con_a", "acct", "t1")
    assert first != stable_id("txn", "con_a", "acct", "t2")
    assert first.startswith("txn_") and len(first) == 30
