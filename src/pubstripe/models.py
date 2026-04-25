from typing import Annotated, Self
from datetime import datetime

from pydantic import BaseModel, StringConstraints, computed_field, field_validator, model_validator

from pubstripe.enums import ProxyScheme, IntentType, ConfirmIntentStatus, CompleteIntentStatus


CardNumber = Annotated[str, StringConstraints(pattern=r"\d{15}|\d{16}")]
ExpMonth = Annotated[str, StringConstraints(pattern=r"\d{2}")]
ExpYear = Annotated[str, StringConstraints(pattern=r"\d{2}|\d{4}")]
CVC = Annotated[str, StringConstraints(pattern=r"\d{3}|\d{4}")]


class CreditCard(BaseModel):
    number: CardNumber
    exp_month: ExpMonth
    exp_year: ExpYear
    cvc: CVC | None = None

    def __str__(self) -> str:
        return f"{self.number}|{self.exp_month}|{self.exp_year}|{self.cvc}"

    @field_validator("exp_month")
    @classmethod
    def validate_exp_month(cls, v: str) -> str:
        if not 1 <= int(v) <= 12:
            raise ValueError("exp_month must be between 01 and 12")
        return v

    @field_validator("exp_year")
    @classmethod
    def validate_exp_year(cls, v: str) -> str:
        now = datetime.now()
        year = int(v)

        if len(v) == 2:
            year += 2000

        if year < now.year:
            raise ValueError("card expired")

        if year > now.year + 20:
            raise ValueError("exp_year too far in future")

        return str(year)

    @model_validator(mode="after")
    def validate_expiry(self) -> "CreditCard":
        now = datetime.now()

        if (int(self.exp_year), int(self.exp_month)) < (now.year, now.month):
            raise ValueError("card expired")

        return self

    @classmethod
    def from_pipe(cls, line: str) -> Self:
        card_parts = line.strip().split("|")

        if len(card_parts) != 4:
            raise ValueError("Invalid pipe format")

        number, exp_month, exp_year, cvc = card_parts

        return cls(
            number=number,
            exp_month=exp_month,
            exp_year=exp_year,
            cvc=cvc,
        )


class Proxy(BaseModel):
    scheme: ProxyScheme
    host: str
    port: int
    user: str | None = None
    password: str | None = None

    @computed_field
    @property
    def url(self) -> str:
        scheme = "socks5h" if self.scheme == "socks5" else self.scheme

        if self.user and self.password:
            return f"{scheme}://{self.user}:{self.password}@{self.host}:{self.port}"

        return f"{scheme}://{self.host}:{self.port}"


class Intent(BaseModel):
    id: str
    type: IntentType

    @computed_field
    @property
    def resource(self) -> str:
        return f"{self.type}s"


class ThreeDSecureRequest(BaseModel):
    transaction_id: str
    source: str


class ThreeDSecureResponse(BaseModel):
    request_status: str
    challenge_mandated: bool
    transaction_status: str


class ConfirmIntentResponse(BaseModel):
    intent: Intent
    payment_method_data: dict[str, str]
    status: ConfirmIntentStatus
    code: str
    message: str
    three_d_secure: ThreeDSecureRequest | None = None


class CompleteIntentResponse(BaseModel):
    intent: Intent
    status: CompleteIntentStatus
    code: str
    message: str