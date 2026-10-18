from typing import Annotated, Self
from datetime import date
from urllib.parse import quote

from pydantic import (
    AliasPath,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
    field_validator,
    model_validator,
)

from pubstripe.enums import (
    ProxyScheme,
    IntentType,
    IntentStatus,
    ThreeDSecureStatus,
)


CardNumber = Annotated[str, StringConstraints(pattern=r"^(?:\d{15}|\d{16})$")]
"""A card number: 15 digits (e.g. Amex) or 16 digits, digits only, no spaces or dashes."""

ExpMonth = Annotated[str, StringConstraints(pattern=r"^\d{2}$")]
"""A two-digit expiration month, zero-padded (e.g. ``"01"`` through ``"12"``)."""

ExpYear = Annotated[str, StringConstraints(pattern=r"^(?:\d{2}|\d{4})$")]
"""A two- or four-digit expiration year (e.g. ``"27"`` or ``"2027"``)."""

CVC = Annotated[str, StringConstraints(pattern=r"^(?:\d{3}|\d{4})$")]
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
        """Return the card in ``number|exp_month|exp_year|cvc`` pipe format.

        A card without a CVC leaves the last field empty, which
        :meth:`from_pipe` reads back as ``cvc=None``.
        """
        return f"{self.number}|{self.exp_month}|{self.exp_year}|{self.cvc or ''}"

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
        """Normalize a two-digit year to four digits.

        Expiry itself (year *and* month together) is checked once, in
        :meth:`validate_expiry`, after normalization has run.
        """
        year = int(v)

        if len(v) == 2:
            year += 2000

        return str(year)

    @model_validator(mode="after")
    def validate_expiry(self) -> "CreditCard":
        """Reject a card whose expiration month/year has already passed."""
        today = date.today()

        if (int(self.exp_year), int(self.exp_month)) < (today.year, today.month):
            raise ValueError("card expired")

        return self

    @classmethod
    def from_pipe(cls, card_pipe: str) -> Self:
        """Build a :class:`CreditCard` from a ``number|exp_month|exp_year|cvc`` string.

        Args:
            card_pipe: The card encoded as four ``|``-separated fields, in
                the same order :meth:`__str__` produces. An empty last
                field means the card has no CVC.

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
            cvc=cvc or None,
        )


class Proxy(BaseModel):
    """Outbound proxy configuration for requests made to Stripe.

    Pass an instance of this to any pubstripe function that accepts a
    ``proxy`` argument to route that request through the proxy.

    Note:
        :attr:`url` embeds the password in plain text, so avoid logging or
        dumping the model.
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
        the proxy side rather than locally. Credentials are percent-encoded,
        and a ``user`` without a ``password`` is still included.
        """
        scheme = "socks5h" if self.scheme == ProxyScheme.SOCKS5 else self.scheme

        if self.user:
            credentials = quote(self.user, safe="")

            if self.password:
                credentials += f":{quote(self.password, safe='')}"

            return f"{scheme}://{credentials}@{self.host}:{self.port}"

        return f"{scheme}://{self.host}:{self.port}"


class StripeError(BaseModel):
    """A Stripe API ``error`` object, as found in an intent's ``last_payment_error``."""

    type: str | None = Field(default=None, description='Error category, e.g. "card_error".')
    code: str | None = Field(default=None, description='Error code, e.g. "card_declined".')
    decline_code: str | None = Field(default=None, description='Issuer decline reason, e.g. "insufficient_funds".')
    message: str | None = Field(default=None, description="Human-readable error message.")
    param: str | None = Field(default=None, description="The request parameter the error relates to, if any.")


class TokenizationResponse(BaseModel):
    """Stripe's reply to creating a payment method or confirmation token.

    Stripe answers with the created object on success and with an ``error``
    object on a card decline, so exactly one of :attr:`id` and :attr:`error`
    is set. A decline is a normal outcome, not an exception: even a valid
    card can be declined.
    """

    id: str | None = Field(default=None, description='The created object\'s ID ("pm_..." or "ctoken_..."), if it succeeded.')
    error: StripeError | None = Field(default=None, description="Why Stripe declined the card, if it did.")


class ThreeDSecureRequest(BaseModel):
    """The ``next_action.use_stripe_sdk`` object Stripe returns when 3D Secure 2 is required.

    Pass this to :func:`pubstripe.three_d_secure.authenticate`
    to complete the challenge. Fields can be set by their Python names or
    their Stripe names.
    """

    model_config = ConfigDict(populate_by_name=True)

    transaction_id: str = Field(
        validation_alias="server_transaction_id",
        description="The 3DS2 server transaction ID (threeDSServerTransID).",
    )
    source: str = Field(
        validation_alias="three_d_secure_2_source",
        description="The 3DS2 source ID used to authenticate the challenge.",
    )


class Intent(BaseModel):
    """A Stripe SetupIntent or PaymentIntent, as returned by the API.

    Returned by every confirm function and by :func:`pubstripe.intent.retrieve`.
    Inspect :attr:`status`: ``succeeded`` means the payment method was
    accepted, ``requires_action`` means :attr:`three_d_secure` must be passed
    to :func:`pubstripe.three_d_secure.authenticate`, and
    ``requires_payment_method`` means it was declined (see
    :attr:`last_payment_error` / :attr:`last_setup_error`).
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(description='The intent\'s Stripe ID, e.g. "pi_..." or "seti_...".')
    type: IntentType = Field(validation_alias="object", description="Whether this is a SetupIntent or a PaymentIntent.")
    status: IntentStatus = Field(description="The intent's Stripe status.")
    client_secret: str | None = Field(default=None, description="The intent's client secret.")
    last_payment_error: StripeError | None = Field(default=None, description="PaymentIntents: the last failure, if any.")
    last_setup_error: StripeError | None = Field(default=None, description="SetupIntents: the last failure, if any.")
    three_d_secure: ThreeDSecureRequest | None = Field(
        default=None,
        validation_alias=AliasPath("next_action", "use_stripe_sdk"),
        description="Present when status is requires_action and Stripe asks for a 3DS2 challenge.",
    )


class ConfirmResponse(BaseModel):
    """Stripe's reply to confirming an intent or a Checkout Session.

    A success carries the :class:`Intent`. A card decline carries the
    :attr:`error`, and also the :attr:`intent` when Stripe attaches one; some
    declines (e.g. an incorrect CVC) come back with no intent at all. A
    decline is a normal outcome, not an exception.
    """

    intent: Intent | None = Field(default=None, description="The intent, if Stripe returned one.")
    error: StripeError | None = Field(default=None, description="Why Stripe declined the card, if it did.")


class CheckoutCustomerAddress(BaseModel):
    """The ``customer.address`` object of a Checkout Session. Any part may be unset."""

    line1: str | None = None
    line2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None


class CheckoutCustomer(BaseModel):
    """The ``customer`` object of a Checkout Session, populated if the merchant attached one."""

    id: str | None = None
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    address: CheckoutCustomerAddress | None = None


class CheckoutSession(BaseModel):
    """The parts of a hosted Checkout Session (``/v1/payment_pages/<id>``) pubstripe uses.

    Returned by :func:`pubstripe.hosted.checkout.get_checkout_session`.
    """

    id: str
    customer: CheckoutCustomer | None = Field(
        default=None,
        description="The customer attached to the session, if any. Stripe checks its email against the payment method's.",
    )
    customer_email: str | None = Field(default=None, description="The email the session was created with, if any.")
    total: int = Field(
        validation_alias=AliasPath("total_summary", "total"),
        description="The amount to pay, in the currency's smallest unit (0 for a trial or setup-mode session); pass it to confirm().",
    )


class ThreeDSecureResponse(BaseModel):
    """Stripe's reply to ``/v1/3ds2/authenticate``.

    Returned by :func:`pubstripe.three_d_secure.authenticate`.
    Only ``source``, ``ares.transStatus``, ``ares.threeDSServerTransID`` and
    ``ares.acsTransID`` are modelled; Stripe doesn't document this endpoint,
    and its other fields are ignored.
    """

    model_config = ConfigDict(populate_by_name=True)

    source: str | None = Field(default=None, description="The 3DS2 source ID this authentication belongs to.")
    trans_status: ThreeDSecureStatus = Field(
        validation_alias=AliasPath("ares", "transStatus"),
        description="The ACS's transaction status code.",
    )
    server_transaction_id: str | None = Field(
        default=None,
        validation_alias=AliasPath("ares", "threeDSServerTransID"),
        description="The 3DS2 server transaction ID, echoed back by the ACS.",
    )
    acs_trans_id: str | None = Field(
        default=None,
        validation_alias=AliasPath("ares", "acsTransID"),
        description="The ACS's own transaction ID for this authentication.",
    )
