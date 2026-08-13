from typing import Any

import phonenumbers
from phonenumbers import carrier
from phonenumbers import geocoder
from phonenumbers import timezone
from phonenumbers.phonenumberutil import NumberParseException

from app.engines.phoneinfoga_engine import PhoneInfogaEngine
from app.engines.calltracer_engine import CallTracerEngine


# ============================================================
# NOXIS PHONE INTELLIGENCE ENGINE
# ============================================================

phoneinfoga_engine = PhoneInfogaEngine()
calltracer_engine = CallTracerEngine()


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

    return type_map.get(
        number_type,
        "Desconocido"
    )


def _extract_public_footprints(
    phoneinfoga_result: dict[str, Any]
) -> list[Any]:
    """
    Extrae referencias públicas útiles de la respuesta
    normalizada de PhoneInfoga.
    """

    footprints: list[Any] = []

    if not isinstance(phoneinfoga_result, dict):
        return footprints

    results = phoneinfoga_result.get("results")

    if not isinstance(results, dict):
        return footprints

    candidate_keys = (
        "footprints",
        "links",
        "urls",
        "results",
    )

    for key in candidate_keys:
        value = results.get(key)

        if isinstance(value, list):
            footprints.extend(value)

    unique = []
    seen = set()

    for item in footprints:
        marker = str(item)

        if marker in seen:
            continue

        seen.add(marker)
        unique.append(item)

    return unique


async def analyze_phone(
    phone_number: str,
    default_region: str = "AR",
) -> dict[str, Any]:

    raw_number = phone_number.strip()

    if not raw_number:
        raise ValueError(
            "El número de teléfono no puede estar vacío."
        )

    # ========================================================
    # PARSEO
    # ========================================================

    try:
        parsed = phonenumbers.parse(
            raw_number,
            None if raw_number.startswith("+") else default_region,
        )

    except NumberParseException as exc:
        raise ValueError(
            f"No se pudo interpretar el número: {exc}"
        )

    # ========================================================
    # VALIDACIÓN
    # ========================================================

    possible = phonenumbers.is_possible_number(parsed)
    valid = phonenumbers.is_valid_number(parsed)

    # ========================================================
    # FORMATOS
    # ========================================================

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

    # ========================================================
    # DATOS TÉCNICOS
    # ========================================================

    region_code = phonenumbers.region_code_for_number(
        parsed
    )

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
        timezone.time_zones_for_number(
            parsed
        )
    )

    number_type = get_number_type(
        parsed
    )

    # ========================================================
    # PHONEINFOGA
    # ========================================================

    phoneinfoga_result: dict[str, Any]

    try:
        phoneinfoga_result = phoneinfoga_engine.search(
            phone_number=e164,
            default_region=default_region,
        )

    except Exception as exc:
        phoneinfoga_result = {
            "status": "error",
            "engine": {
                "id": "phoneinfoga",
                "name": "PhoneInfoga",
                "mode": "live",
            },
            "error": "phoneinfoga_exception",
            "message": str(exc),
        }

    public_footprints = _extract_public_footprints(
        phoneinfoga_result
    )

    # ========================================================
    # CALLTRACER — REPUTACIÓN
    # ========================================================

    try:
        calltracer_result = calltracer_engine.search(
            phone_number=e164,
            default_region=default_region,
        )

    except Exception as exc:
        calltracer_result = {
            "status": "error",
            "engine": {
                "id": "calltracer",
                "name": "CallTracer",
                "mode": "live",
            },
            "reported": False,
            "spam_score": None,
            "reports_count": 0,
            "error": "calltracer_exception",
            "message": str(exc),
        }

    # ========================================================
    # RESPUESTA FINAL
    # ========================================================

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
            "location_description": (
                location or None
            ),
            "carrier": (
                carrier_name or None
            ),
            "line_type": number_type,
            "timezones": timezones,
        },

        "engines": {
            "technical": {
                "id": "phonenumbers",
                "name": "Google libphonenumber",
                "mode": "live",
                "status": "completed",
            },

            "osint": {
                "id": "phoneinfoga",
                "name": "PhoneInfoga",
                "mode": "live",
                "status": phoneinfoga_result.get(
                    "status",
                    "unknown",
                ),
            },

            "reputation": {
                "id": "calltracer",
                "name": "CallTracer",
                "mode": "live",
                "status": calltracer_result.get(
                    "status",
                    "unknown",
                ),
            },
        },

        "phoneinfoga": phoneinfoga_result,

        "calltracer": calltracer_result,

        "public_footprints": public_footprints,

        "reputation": {
            "status": "not_checked",
        },
    }
