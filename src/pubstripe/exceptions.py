

class StripeException(Exception):
    """Base class for every exception raised by pubstripe.

    Catch this to handle any Stripe-related failure without needing to
    know which specific subclass was raised.
    """


class InvalidRequestError(StripeException):
    """Raised when Stripe rejects a request as malformed (HTTP 400).

    The exception message is Stripe's own ``error.message`` field, so it
    already describes what was wrong with the request.
    """


class InvalidPublishableKey(StripeException):
    """Raised when Stripe rejects the publishable key used for a request (HTTP 401).

    This usually means the key is missing, revoked, or does not belong to
    the account that owns the resource being accessed.
    """


class InvalidClientSecret(StripeException, ValueError):
    """Raised when a client secret cannot be parsed into an intent.

    A valid client secret starts with ``seti_`` (a SetupIntent) or ``pi_``
    (a PaymentIntent) followed by ``_secret_...``. Anything else raises
    this error. It also subclasses :class:`ValueError`.
    """


class StripeJsUnavailable(StripeException):
    """Raised when the current Stripe.js build hash can't be determined.

    Tokenization needs the hash for its ``payment_user_agent``. See
    :func:`pubstripe.stripe_js.get_version`.
    """
