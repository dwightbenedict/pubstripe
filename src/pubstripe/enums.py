from enum import StrEnum


class ProxyScheme(StrEnum):
    """Supported schemes for an outbound proxy. See :class:`pubstripe.models.Proxy`."""

    HTTP = "http"
    SOCKS5 = "socks5"


class IntentType(StrEnum):
    """The two kinds of Stripe intent, matching the API's ``object`` field."""

    SETUP_INTENT = "setup_intent"
    PAYMENT_INTENT = "payment_intent"


class IntentStatus(StrEnum):
    """An intent's ``status`` as Stripe reports it."""

    REQUIRES_PAYMENT_METHOD = "requires_payment_method"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    REQUIRES_ACTION = "requires_action"
    PROCESSING = "processing"
    REQUIRES_CAPTURE = "requires_capture"
    CANCELED = "canceled"
    SUCCEEDED = "succeeded"


class ThreeDSecureStatus(StrEnum):
    """The ACS's ``transStatus`` code, as defined by the EMV 3-D Secure standard.

    The values are the codes Stripe returns in ``ares.transStatus``.
    """

    AUTHENTICATED = "Y"
    """Authentication or account verification successful."""
    NOT_AUTHENTICATED = "N"
    """Not authenticated or account not verified; the transaction was denied."""
    UNAVAILABLE = "U"
    """Authentication or verification could not be performed."""
    ATTEMPTED = "A"
    """Attempts processing performed; not authenticated, but a proof of attempt exists."""
    CHALLENGE_REQUIRED = "C"
    """The cardholder must complete an additional challenge."""
    DECOUPLED = "D"
    """A decoupled challenge is required, and authentication will complete asynchronously."""
    REJECTED = "R"
    """Authentication or verification rejected; the issuer asks that it not be attempted."""
    INFORMATIONAL = "I"
    """Informational only."""
