

class StripeException(Exception):
    pass


class InvalidRequestError(StripeException):
    pass


class InvalidPublishableKey(StripeException):
    pass


class InvalidPaymentMethod(StripeException):
    pass


class InvalidClientSecret(StripeException):
    pass