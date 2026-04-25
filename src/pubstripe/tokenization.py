from pubstripe.client.request import request_stripe
from pubstripe.models import CreditCard, Proxy
from pubstripe.exceptions import InvalidPaymentMethod


async def create_token(
        uri: str,
        payment_config: dict[str, str | int],
        proxy: Proxy | None = None
) -> str:
    response = await request_stripe("POST", uri, data=payment_config, proxy=proxy)
    data = response.json()

    if response.status_code == 402:
        raise InvalidPaymentMethod(data["error"]["message"])

    response.raise_for_status()
    return data["id"]


async def create_payment_method(
        card: CreditCard,
        publishable_key: str,
        proxy: Proxy | None = None
) -> str:
    uri = "/v1/payment_methods"
    payload = {
        "type": "card",
        "card[number]": card.number,
        "card[exp_month]": card.exp_month,
        "card[exp_year]": card.exp_year,
        "key": publishable_key,
        "payment_user_agent": "stripe.js/668d00c08a; stripe-js-v3/668d00c08a; payment-element; deferred-intent"
    }

    if card.cvc:
        payload["card[cvc]"] = card.cvc

    return await create_token(uri, payload, proxy=proxy)


async def create_confirmation_token(
        card: CreditCard,
        publishable_key: str,
        proxy: Proxy | None = None
) -> str:
    uri = "/v1/confirmation_tokens"
    payload = {
        "payment_method_data[type]": "card",
        "payment_method_data[card][number]": card.number,
        "payment_method_data[card][exp_year]": card.exp_year,
        "payment_method_data[card][exp_month]": card.exp_month,
        "payment_method_data[payment_user_agent]": "stripe.js/668d00c08a; stripe-js-v3/668d00c08a; payment-element; deferred-intent; autopm",
        "key": publishable_key,
    }

    if card.cvc:
        payload["payment_method_data[card][cvc]"] = card.cvc


    return await create_token(uri, payload, proxy=proxy)