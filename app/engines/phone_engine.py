from typing import Any

import phonenumbers
from phonenumbers import carrier
from phonenumbers import geocoder
from phonenumbers import timezone
from phonenumbers.phonenumberutil import NumberParseException


def get_number_type(parsed_number) -> str:
    number_type = phonenumbers.number_type(parsed_number)

    type_map = {
        phonenumbers.PhoneNumberType.FIXED_LINE: "Fijo",
        phonenumbers.PhoneNumberType.MOBILE: "Móvil",
        phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "Fijo o móvil",
        phonenumbers.PhoneNumberType.TOLL_FREE: "Gratuito",
        phonenumbers.PhoneNumberType.PREMIUM_RATE: "Tarifa premium",
        phonenumbers.PhoneNumberType.SHARED_COST: "Costo compartido",
        phonenumbers.PhoneNumberType.VOIP: "VoIP",
        phonenumbers.PhoneNumberType.PERSONAL_NUMBER: "Número personal",
        phonenumbers.PhoneNumberType.PAGER: "Pager",
        phonenumbers.PhoneNumberType.UAN: "UAN",
        phonenumbers.PhoneNumberType.VOICEMAIL: "Buzón de voz",
        phonenumbers.PhoneNumberType.UNKNOWN: "Desconocido",
    }

    return type_map.get(number_type, "Desconocido")


async def analyze_phone(
    phone_number: str,
    default_region: str = "AR",
) -> dict[str, Any]:

    raw_number = phone_number.strip()

    if not raw_number:
        raise ValueError("El número de teléfono no puede estar vacío.")

    try:
        parsed = phonenumbers.parse(
            raw_number,
            None if raw_number.startswith("+") else default_region,
        )

    except NumberParseException as exc:
        raise ValueError(
            f"No se pudo interpretar el número: {exc}"
        )

    possible = phonenumbers.is_possible_number(parsed)
    valid = phonenumbers.is_valid_number(parsed)

    e164 = phonenumbers.format_number(
        parsed,
        phonenumbers.PhoneNumberFormat.E164,
    )

    international = phonenumbers.format_number(
        parsed,
        phonenumbers.PhoneNumberFormat.INTERNATIONAL,
    )

    national = phonenumbers.format_number(
        parsed,
        phonenumbers.PhoneNumberFormat.NATIONAL,
    )

    region_code = phonenumbers.region_code_for_number(parsed)

    country_code = parsed.country_code

    location = geocoder.description_for_number(
        parsed,
        "es",
    )

    carrier_name = carrier.name_for_number(
        parsed,
        "es",
    )

    timezones = list(
        timezone.time_zones_for_number(parsed)
    )

    number_type = get_number_type(parsed)

    return {
        "input": raw_number,

        "normalized": {
            "e164": e164,
            "international": international,
            "national": national,
        },

        "validation": {
            "possible": possible,
            "valid": valid,
        },

        "country": {
            "region_code": region_code,
            "country_calling_code": country_code,
        },

        "technical": {
            "location_description": location or None,
            "carrier": carrier_name or None,
            "line_type": number_type,
            "timezones": timezones,
        },

        "engine": {
            "id": "phonenumbers",
            "name": "Google libphonenumber",
            "mode": "live",
        },

        "public_footprints": [],

        "reputation": {
            "status": "not_checked",
        },
    }
