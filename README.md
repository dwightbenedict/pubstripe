# pubstripe

Process payments via Stripe's API using only a publishable key.

pubstripe re-implements the handful of Stripe.js flows needed to tokenize a
card, confirm a SetupIntent/PaymentIntent, and complete 3D Secure 2
authentication -- all with just a publishable key, no secret key or the
official Stripe SDK required.

## Install

```bash
pip install pubstripe
```

Requires Python 3.13+.

## Typical flow

1. Build a card with `CreditCard`.
2. Confirm an intent with `confirm_intent_with_credit_card` (or tokenize
   first with `create_payment_method` / `create_confirmation_token` and
   confirm with `confirm_intent_with_payment_method`).
3. If the response's `status` is `REQUIRES_ACTION`, complete the challenge
   with `authenticate_three_d_secure`, then call
   `complete_intent_after_3ds2` to get the final result.

## Example

```python
import asyncio
from pubstripe import CreditCard, confirm_intent_with_credit_card


async def main():
    card = CreditCard(number="4242424242424242", exp_month="12", exp_year="2030", cvc="123")
    result = await confirm_intent_with_credit_card(
        card=card,
        client_secret="pi_..._secret_...",
        publishable_key="pk_test_...",
    )
    print(result.status, result.message)


asyncio.run(main())
```

Everything above is importable directly from the `pubstripe` package, so
`from pubstripe import CreditCard, confirm_intent_with_credit_card` works
without reaching into submodules.

## Handling 3D Secure 2

```python
if result.status == ConfirmIntentStatus.REQUIRES_ACTION:
    status = await authenticate_three_d_secure(
        request=result.three_d_secure,
        publishable_key="pk_test_...",
    )
    final = await complete_intent_after_3ds2(
        client_secret="pi_..._secret_...",
        publishable_key="pk_test_...",
    )
```

## Exceptions

All exceptions inherit from `StripeException`:

- `InvalidRequestError` -- Stripe rejected the request as malformed (HTTP 400).
- `InvalidPublishableKey` -- the publishable key was missing/revoked/wrong (HTTP 401).
- `InvalidPaymentMethod` -- Stripe declined the card during tokenization or confirmation (HTTP 402).
- `InvalidClientSecret` -- a client secret couldn't be parsed into an intent.
