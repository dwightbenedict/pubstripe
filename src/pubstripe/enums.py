"""Enumerations shared across pubstripe's models and functions."""

from enum import StrEnum


class ProxyScheme(StrEnum):
    """Supported schemes for an outbound proxy. See :class:`pubstripe.models.Proxy`."""

    HTTP = "http"
    SOCKS5 = "socks5"


class IntentType(StrEnum):
    """The two kinds of Stripe intent that pubstripe can confirm.

    Determined automatically from a client secret's prefix by
    :func:`pubstripe.intent.intent_from_client_secret`.
    """

    SETUP_INTENT = "setup_intent"
    PAYMENT_INTENT = "payment_intent"


class ConfirmIntentStatus(StrEnum):
    """Outcome of :func:`pubstripe.intent.confirm_intent`."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REQUIRES_ACTION = "requires_action"


class CompleteIntentStatus(StrEnum):
    """Outcome of :func:`pubstripe.intent.complete_intent_after_3ds2`."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ThreeDSecureStatus(StrEnum):
    """Result of a 3D Secure 2 authentication challenge.

    Returned by :func:`pubstripe.three_d_secure.authenticate_three_d_secure`,
    mapped from Stripe's single-letter ACS ``transStatus`` code.
    """

    FRICTIONLESS = "frictionless"
    """Authenticated without showing the cardholder a challenge (``transStatus`` "Y")."""
    FAILED = "failed"
    """Authentication was attempted but failed (``transStatus`` "N")."""
    UNAVAILABLE = "unavailable"
    """3D Secure is not available for this card/issuer (``transStatus`` "U")."""
    ATTEMPTED = "attempted"
    """Authentication was attempted; liability shift may still apply (``transStatus`` "A")."""
    CHALLENGE = "challenge"
    """The cardholder must complete an interactive challenge (``transStatus`` "C")."""
    REJECTED = "rejected"
    """The issuer rejected the authentication (``transStatus`` "R")."""
    DECOUPLED = "decoupled"
    """Authentication will be completed asynchronously (``transStatus`` "D")."""
    INFORMATIONAL = "informational"
    """Informational only; no decision was made (``transStatus`` "I")."""
