# pubstripe

Process payments via Stripe's API using only a publishable key.

pubstripe re-implements the handful of Stripe.js flows needed to tokenize a
card, confirm a SetupIntent/PaymentIntent or a hosted Checkout Session, and
complete 3D Secure 2 authentication -- all with just a publishable key, no
secret key or the official Stripe SDK required.

## Install

```bash
pip install pubstripe
```

Requires Python 3.13+.

## Typical flow

1. Build a card with `CreditCard` (or `CreditCard.from_pipe("number|mm|yyyy|cvc")`).
2. Confirm it:
   - **Intent** (you hold a `pi_..._secret_...` / `seti_..._secret_...`
     client secret): `confirm_with_credit_card`, or tokenize first with
     `create_payment_method` / `create_confirmation_token` and use
     `confirm_with_payment_method`.
   - **Hosted Checkout** (you hold a `checkout.stripe.com` URL): parse it with
     `CheckoutContext.from_url`, read the session with `get_checkout_session`, tokenize
     with `BillingDetails.from_checkout_session`, then `confirm_checkout`.
3. If the response's `intent.status` is `requires_action`, complete the challenge
   with `authenticate_three_d_secure`, then call `retrieve` with the client
   secret to get the final result.

Everything is `async` and importable straight from `pubstripe`.

## Confirm an intent

```python
import asyncio
from pubstripe import CreditCard, confirm_with_credit_card


async def main():
    card = CreditCard(number="4242424242424242", exp_month="12", exp_year="2030", cvc="123")
    result = await confirm_with_credit_card(
        card=card,
        client_secret="pi_..._secret_...",
        publishable_key="pk_test_...",
    )
    print(result.error or result.intent.status)


asyncio.run(main())
```

The result is a `ConfirmResponse` with an `intent` (a direct mirror of Stripe's
intent object: `id`, `type`, `status`, `client_secret`, `last_payment_error`,
`last_setup_error`, `three_d_secure`) or an `error` (Stripe's error object:
`code`, `decline_code`, `message`, ...). pubstripe adds no status or message of
its own:

```python
from pubstripe import IntentStatus

if result.error:  # declined, e.g. incorrect CVC; result.intent may also be set
    print(result.error.decline_code or result.error.code, result.error.message)
elif result.intent.status == IntentStatus.SUCCEEDED: ...
elif result.intent.status == IntentStatus.REQUIRES_ACTION: ...  # see 3D Secure below
```

A card decline is **returned** this way, not raised, and some declines (an
incorrect CVC, for instance) come back with no intent at all. Tokenization works the
same way: `create_payment_method` and `create_confirmation_token` return a
`TokenizationResponse` with either `id` or `error` set.

## Confirm a hosted Checkout Session

```python
from pubstripe import (
    BillingDetails, CheckoutContext, confirm_checkout, create_payment_method, get_checkout_session,
)

ctx = CheckoutContext.from_url("https://checkout.stripe.com/c/pay/cs_live_...#...")
session = await get_checkout_session(ctx)
details = BillingDetails.from_checkout_session(session)
token = await create_payment_method(card, ctx.publishable_key, billing_details=details)
if token.error:
    ...  # declined: token.error.decline_code / token.error.message
else:
    result = await confirm_checkout(token.id, session.total, ctx)
```

If the session has a customer attached, Stripe requires the payment method's
billing email to match theirs (otherwise `InvalidRequestError`:
`customer_and_confirmation_email_mismatch`). `from_checkout_session` copies
the customer's email, name and address and randomizes whatever is missing.

The result is a `ConfirmResponse` too; pass `intent.client_secret` to `retrieve`
after a 3DS2 challenge.

## Billing details

`create_payment_method` and `create_confirmation_token` send billing details
with the card. If you don't pass any, random US details are generated with
[Faker](https://faker.readthedocs.io/). Pass your own to control them; any
field you leave out is still randomized:

```python
from pubstripe import Address, BillingDetails

details = BillingDetails(name="Ada Lovelace", address=Address(postal_code="10001"))
token = await create_payment_method(card, "pk_test_...", billing_details=details)
```

## Handling 3D Secure 2

```python
from pubstripe import IntentStatus, authenticate_three_d_secure, retrieve

if result.intent and result.intent.status == IntentStatus.REQUIRES_ACTION:
    three_d_secure = await authenticate_three_d_secure(
        request=result.intent.three_d_secure,
        publishable_key="pk_test_...",
    )
    final = await retrieve(
        client_secret="pi_..._secret_...",
        publishable_key="pk_test_...",
    )
    print(three_d_secure.trans_status, final.status)
```

## Proxies

Every network function takes an optional `proxy`:

```python
from pubstripe import Proxy, ProxyScheme

proxy = Proxy(scheme=ProxyScheme.SOCKS5, host="127.0.0.1", port=1080, user="u", password="p")
await confirm_with_credit_card(card, client_secret, publishable_key, proxy=proxy)
```

SOCKS5 proxies resolve DNS remotely (`socks5h`). `Proxy.url` contains the
password in plain text, so don't log it.

## Models

Response models mirror Stripe's JSON and are populated with pydantic aliases
(`validation_alias` / `AliasPath`), so `Intent.model_validate(stripe_json)`
works directly. The one renamed field is `Intent.three_d_secure`, which reads
`next_action.use_stripe_sdk`. `CreditCard` and `Proxy` are inputs you build.

## Exceptions

All exceptions inherit from `StripeException`:

- `InvalidRequestError` -- Stripe rejected the request as malformed (HTTP 400).
- `InvalidPublishableKey` -- the publishable key was missing/revoked/wrong (HTTP 401).
- `InvalidClientSecret` -- a client secret couldn't be parsed into an intent
  (also a `ValueError`).
- `StripeJsUnavailable` -- the current Stripe.js build (needed for tokenization's
  `payment_user_agent`) couldn't be fetched from `js.stripe.com`.

Card declines are not exceptions; they come back in the response (see above).
Other HTTP errors (e.g. 404, 5xx) surface as `curl_cffi` `HTTPError`s.
Transient network failures are retried up to 3 times.

## Development

```bash
pip install -e ".[dev]"
```
