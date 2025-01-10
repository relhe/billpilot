import phonenumbers
from pycountry import countries, currencies
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from typing import Optional, Literal
from datetime import datetime, date


class Payment(BaseModel):
    payee_first_name: str
    payee_last_name: str
    payee_payment_status: Literal["completed", "due_now", "overdue", "pending"]
    payee_added_date_utc: datetime
    payee_due_date: date
    payee_address_line_1: str
    payee_address_line_2: Optional[str]
    payee_city: str
    payee_country: str
    payee_province_or_state: Optional[str]
    payee_postal_code: str
    payee_phone_number: str
    payee_email: EmailStr
    currency: str
    discount_percent: Optional[float] = Field(default=0.00, ge=0.00, le=100.00)
    tax_percent: Optional[float] = Field(default=0.00, ge=00.00, le=100.00)
    due_amount: float
    total_due: float = 0.0

    # dynamic calculation of total_due field based on due_amount,
    # discount_percent, and tax_percent
    model_config = ConfigDict(validate_assignment=True)

    @field_validator("payee_country")
    @classmethod
    def validate_country_code(cls, value):
        """
        Validates the payee's country code using ISO 3166-1 alpha-2 standard.

        Parameters:
        value (str): The country code to be validated.

        Returns:
        str: The validated country code.

        Raises:
        ValueError: If the provided country code is not valid according\
            to ISO 3166-1 alpha-2 standard.
        """
        valid_country_codes = {country.alpha_2 for country in countries}
        if value not in valid_country_codes:
            raise ValueError(
                f"{value} is not a valid ISO 3166-1 alpha-2 country code"
            )
        return value

    @field_validator("payee_phone_number")
    @classmethod
    def validate_phone_number(cls, value):
        """
        Validates the payee's phone number using the phonenumbers library.

        Parameters:
        value (str): The phone number to be validated.

        Returns:
        str: The validated phone number in E.164 format.

        Raises:
        ValueError: If the provided phone number is not valid according\
            to E.164 or if it cannot be parsed.
        """
        try:
            phone_number = phonenumbers.parse(value)
            # Validate the phone number
            if not phonenumbers.is_valid_number(phone_number):
                raise ValueError(f"{value} is not a valid E.164 phone number")
            # Ensure the phone number is in E.164 format
            return phonenumbers.format_number(
                phone_number, phonenumbers.PhoneNumberFormat.E164)
        except phonenumbers.NumberParseException as e:
            raise ValueError(f"{value} is not a valid phone number: {e}")

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value):
        """
        Validates the currency code using ISO 4217 standard.

        Parameters:
        value (str): The currency code to be validated.

        Returns:
        str: The validated currency code.

        Raises:
        ValueError: If the provided currency code is not valid according\
            to ISO 4217 standard.

        This method checks if the provided currency code\
            is a valid ISO 4217 currency code.
        If the code is not valid, it raises a ValueError with\
            an appropriate error message.
        Otherwise, it returns the validated currency code.
        """
        valid_currencies = {currency.alpha_3 for currency in currencies}
        if value not in valid_currencies:
            raise ValueError(f"{value} is not a valid ISO 4217 currency code")
        return value

    @field_validator(
        "discount_percent", "tax_percent", "due_amount", mode="before")
    @classmethod
    def round_two_decimal_points(cls, value):
        if value is not None:
            return round(value, 2)
        return value

    @field_validator("total_due", mode="after")
    @classmethod
    def calculate_total_due(cls, values):
        due_amount = values.get("due_amount", 0.0)
        discount_percent = values.get("discount_percent", 0.0)
        tax_percent = values.get("tax_percent", 0.0)

        discount = due_amount * (discount_percent / 100)
        tax = due_amount * (tax_percent / 100)

        return round(due_amount - discount + tax, 2)
