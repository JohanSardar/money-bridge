from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from money_bridge.kernel.errors import ErrorCode, MoneyBridgeError


def parse_decimal(text: str | int | Decimal) -> Decimal:
    if isinstance(text, bool | float):
        raise MoneyBridgeError(ErrorCode.INVALID_REQUEST, "amounts must be decimal strings, not floats")
    try:
        value = Decimal(text)
    except InvalidOperation as error:
        raise MoneyBridgeError(ErrorCode.INVALID_REQUEST, f"not a decimal amount: {text!r}") from error
    if not value.is_finite():
        raise MoneyBridgeError(ErrorCode.INVALID_REQUEST, f"not a finite amount: {text!r}")
    return value


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    @classmethod
    def of(cls, amount: str | int | Decimal, currency: str) -> "Money":
        code = currency.strip().upper()
        if not code:
            raise MoneyBridgeError(ErrorCode.INVALID_REQUEST, "currency is required")
        return cls(parse_decimal(amount), code)

    def to_dict(self) -> dict[str, str]:
        return {"amount": format(self.amount, "f"), "currency": self.currency}
