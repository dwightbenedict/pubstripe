from dataclasses import dataclass, field
from typing import Any, Self, TYPE_CHECKING

from faker import Faker

if TYPE_CHECKING:
    from pubstripe.models import CheckoutSession


_faker = Faker("en_US")


def _given(**values: Any) -> dict[str, Any]:
    """Keep only the values that are set, so the dataclass defaults fill in the rest."""
    return {key: value for key, value in values.items() if value}


def _state() -> str:
    """A two-letter US state code, which is what Stripe expects."""
    return _faker.state_abbr(include_territories=False)


@dataclass
class Address:
    """A billing address. Defaults to a random US address."""

    line1: str = field(default_factory=_faker.street_address)
    city: str = field(default_factory=_faker.city)
    state: str = field(default_factory=_state)
    country: str = "US"
    """A two-letter ISO 3166-1 country code."""
    postal_code: str = field(default_factory=_faker.postcode)


@dataclass
class BillingDetails:
    """The cardholder's name, contact details and address.

    Any field left out is filled with a random value, and
    ``BillingDetails()`` is a fully random identity.
    """

    name: str = field(default_factory=_faker.name)
    email: str = field(default_factory=_faker.free_email)
    address: Address = field(default_factory=Address)

    def to_params(self, prefix: str) -> dict[str, str]:
        """Flatten into Stripe's bracketed form keys.

        Args:
            prefix: The key the ``billing_details`` object lives under, e.g.
                ``"billing_details"`` or
                ``"payment_method_data[billing_details]"``.

        Returns:
            For example ``{"billing_details[name]": "...",
            "billing_details[address][line1]": "...", ...}``.
        """
        return {
            f"{prefix}[name]": self.name,
            f"{prefix}[email]": self.email,
            f"{prefix}[address][line1]": self.address.line1,
            f"{prefix}[address][city]": self.address.city,
            f"{prefix}[address][state]": self.address.state,
            f"{prefix}[address][country]": self.address.country,
            f"{prefix}[address][postal_code]": self.address.postal_code,
        }

    @classmethod
    def from_checkout_session(cls, session: "CheckoutSession") -> Self:
        """Build billing details that agree with a Checkout Session's customer.

        Stripe rejects a confirmation whose payment method email differs from
        the session's customer email (``customer_and_confirmation_email_mismatch``),
        so use this for hosted Checkout. Whatever the session's customer
        has (name, email, address parts) is used; anything it lacks is
        randomized.

        Args:
            session: The session from :func:`pubstripe.hosted.checkout.get_checkout_session`.

        Returns:
            The :class:`BillingDetails`.
        """
        customer = session.customer
        address = customer.address if customer else None

        return cls(**_given(
            name=customer.name if customer else None,
            email=(customer.email if customer else None) or session.customer_email,
            address=Address(**_given(
                line1=address.line1,
                city=address.city,
                state=address.state,
                country=address.country,
                postal_code=address.postal_code,
            )) if address else None,
        ))
