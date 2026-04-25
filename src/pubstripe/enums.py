from enum import StrEnum


class ProxyScheme(StrEnum):
    HTTP = "http"
    SOCKS5 = "socks5"


class IntentType(StrEnum):
    SETUP_INTENT = "setup_intent"
    PAYMENT_INTENT = "payment_intent"


class ConfirmIntentStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REQUIRES_ACTION = "requires_action"


class CompleteIntentStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"