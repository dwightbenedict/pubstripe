"""Pydantic data models used throughout pubstripe.

These models validate and normalize the values pubstripe sends to and
receives from Stripe's API: credit card details, proxy configuration,
intents, and the responses returned by :mod:`pubstripe.intent`.
"""

from typing import Annotated, Self
from datetime import datetime

from pydantic import BaseModel, Field, StringConstraints, computed_field, field_validator, model_validator

from pubstripe.enums import (
    ProxyScheme,
    IntentType,
    ConfirmIntentStatus,
    CompleteIntentStatus
)


CardNumber = Annotated[str, StringConstraints(pattern=r"\d{15}|\d{16}")]
"""A card number: 15 digits (e.g. Amex) or 16 digits, digits only, no spaces or dashes."""

ExpMonth = Annotated[str, StringConstraints(pattern=r"\d{2}")]
"""A two-digit expiration month, zero-padded (e.g. ``"01"`` through ``"12"``)."""

ExpYear = Annotated[str, StringConstraints(pattern=r"\d{2}|\d{4}")]
"""A two- or four-digit expiration year (e.g. ``"27"`` or ``"2027"``)."""

CVC = Annotated[str, StringConstraints(pattern=r"\d{3}|\d{4}")]
"""A card verification code: 3 digits, or 4 digits for Amex."""


class CreditCard(BaseModel):
    """A raw credit card, validated for shape and expiry before it is sent to Stripe.

    Build one directly, or from a pipe-delimited string with :meth:`from_pipe`.

    Examples:
        >>> CreditCard(number="4242424242424242", exp_month="12", exp_year="2030", cvc="123")
        >>> CreditCard.from_pipe("4242424242424242|12|2030|123")
    """

    number: CardNumber = Field(description='The card number, digits only (15 or 16 digits).')
    exp_month: ExpMonth = Field(description='Two-digit expiration month, e.g. "01"-"12".')
    exp_year: ExpYear = Field(description='Two- or four-digit expiration year, e.g. "27" or "2027".')
    cvc: CVC | None = Field(default=None, description='Card verification code (3 or 4 digits). Optional.')

    def __str__(self) -> str:
        """Return the card in ``number|exp_month|exp_year|cvc`` pipe format."""
        return f"{self.number}|{self.exp_month}|{self.exp_year}|{self.cvc}"

    @field_validator("exp_month")
    @classmethod
    def validate_exp_month(cls, v: str) -> str:
        """Reject an ``exp_month`` outside the valid ``01``-``12`` range."""
        if not 1 <= int(v) <= 12:
            raise ValueError("exp_month must be between 01 and 12")
        return v

    @field_validator("exp_year")
    @classmethod
    def validate_exp_year(cls, v: str) -> str:
        """Normalize a two-digit year to four digits and reject expired or implausible years."""
        now = datetime.now()
        year = int(v)

        if len(v) == 2:
            year += 2000

        if year < now.year:
            raise ValueError("card expired")

        if year > now.year + 20:
            raise ValueError("exp_year too far in future")

        return str(year)

    @model_validator(mode="after")
    def validate_expiry(self) -> "CreditCard":
        """Reject a card whose expiration month/year has already passed."""
        now = datetime.now()

        if (int(self.exp_year), int(self.exp_month)) < (now.year, now.month):
            raise ValueError("card expired")

        return self

    @classmethod
    def from_pipe(cls, card_pipe: str) -> Self:
        """Build a :class:`CreditCard` from a ``number|exp_month|exp_year|cvc`` string.

        Args:
            card_pipe: The card encoded as four ``|``-separated fields, in
                the same order :meth:`__str__` produces.

        Returns:
            The parsed and validated :class:`CreditCard`.

        Raises:
            ValueError: If ``card_pipe`` does not split into exactly four
                parts, or if any field fails validation.
        """
        card_parts = card_pipe.strip().split("|")

        if len(card_parts) != 4:
            raise ValueError("Invalid pipe format")

        number, exp_month, exp_year, cvc = card_parts

        return cls(
            number=number,
            exp_month=exp_month,
            exp_year=exp_year,
            cvc=cvc,
        )


class Proxy(BaseModel):
    """Outbound proxy configuration for requests made to Stripe.

    Pass an instance of this to any pubstripe function that accepts a
    ``proxy`` argument to route that request through the proxy.
    """

    scheme: ProxyScheme = Field(description="The proxy protocol: HTTP or SOCKS5.")
    host: str = Field(description="Proxy hostname or IP address.")
    port: int = Field(description="Proxy port.")
    user: str | None = Field(default=None, description="Username for proxy authentication, if required.")
    password: str | None = Field(default=None, description="Password for proxy authentication, if required.")

    @computed_field
    @property
    def url(self) -> str:
        """The proxy as a connection URL, e.g. ``socks5h://user:pass@host:port``.

        SOCKS5 proxies are given as ``socks5h`` so DNS resolution happens on
        the proxy side rather than locally.
        """
        scheme = "socks5h" if self.scheme == "socks5" else self.scheme

        if self.user and self.password:
            return f"{scheme}://{self.user}:{self.password}@{self.host}:{self.port}"

        return f"{scheme}://{self.host}:{self.port}"


class Intent(BaseModel):
    """A Stripe SetupIntent or PaymentIntent identified by a client secret.

    Build one from a raw client secret with
    :func:`pubstripe.intent.intent_from_client_secret`.
    """

    id: str = Field(description='The intent\'s Stripe ID, e.g. "pi_..." or "seti_...".')
    type: IntentType = Field(description="Whether this is a SetupIntent or a PaymentIntent.")

    @computed_field
    @property
    def resource(self) -> str:
        """The plural API resource path segment for this intent, e.g. ``"payment_intents"``."""
        return f"{self.type}s"


class ThreeDSecureRequest(BaseModel):
    """The data Stripe returns when an intent confirmation requires 3D Secure 2.

    Pass this to :func:`pubstripe.three_d_secure.authenticate_three_d_secure`
    to complete the challenge.
    """

    transaction_id: str = Field(description="The 3DS2 server transaction ID (threeDSServerTransID).")
    source: str = Field(description="The 3DS2 source ID used to authenticate the challenge.")


class ConfirmIntentResponse(BaseModel):
    """The result of :func:`pubstripe.intent.confirm_intent`."""

    intent: Intent = Field(description="The intent that was confirmed.")
    payment_method_data: dict[str, str] = Field(description="The raw payment method fields sent to Stripe.")
    status: ConfirmIntentStatus = Field(description="Whether confirmation succeeded, failed, or needs 3D Secure.")
    code: str = Field(description="Stripe's status or decline/error code for this outcome.")
    message: str = Field(description="A human-readable description of the outcome.")
    three_d_secure: ThreeDSecureRequest | None = Field(
        default=None,
        description="Present only when status is REQUIRES_ACTION; pass it to authenticate_three_d_secure().",
    )


class CompleteIntentResponse(BaseModel):
    """The result of :func:`pubstripe.intent.complete_intent_after_3ds2`."""

    intent: Intent = Field(description="The intent that was checked.")
    status: CompleteIntentStatus = Field(description="Whether the intent ultimately succeeded or failed.")
    code: str = Field(description="Stripe's status or decline/error code for this outcome.")
    message: str = Field(description="A human-readable description of the outcome.")
