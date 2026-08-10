from typing import Any
from urllib.parse import quote

import httpx


PHONEINFOGA_BASE_URL = "https://noxis-phoneinfoga.onrender.com"


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
) -> dict[str, Any] | list[Any] | None:

    try:
        response = await client.get(url)

        if response.status_code == 404:
            return None

        response.raise_for_status()

        if not response.content:
            return None

        return response.json()

    except (
        httpx.HTTPError,
        ValueError,
    ):
        return None


async def analyze_phoneinfoga(
    phone_number: str,
) -> dict[str, Any]:

    number = phone_number.strip()

    if not number:
        raise ValueError(
            "El número de teléfono no puede estar vacío."
        )

    encoded_number = quote(
        number,
        safe="",
    )

    base = PHONEINFOGA_BASE_URL.rstrip("/")

    endpoints = {
        "validation": (
            f"{base}/api/numbers/"
            f"{encoded_number}/validate"
        ),
        "local": (
            f"{base}/api/numbers/"
            f"{encoded_number}/scan/local"
        ),
        "ovh": (
            f"{base}/api/numbers/"
            f"{encoded_number}/scan/ovh"
        ),
        "google_search": (
            f"{base}/api/numbers/"
            f"{encoded_number}/scan/googlesearch"
        ),
        "numverify": (
            f"{base}/api/numbers/"
            f"{encoded_number}/scan/numverify"
        ),
    }

    results: dict[str, Any] = {}

    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={
            "Accept": "application/json",
            "User-Agent": "NOXIS-PhoneIntelligence",
        },
    ) as client:

        for scanner_name, url in endpoints.items():

            data = await _get_json(
                client=client,
                url=url,
            )

            if data is not None:
                results[scanner_name] = data

    footprints = []

    google_data = results.get(
        "google_search"
    )

    if isinstance(google_data, dict):

        for key in (
            "results",
            "links",
            "urls",
            "footprints",
        ):
            value = google_data.get(key)

            if isinstance(value, list):
                footprints.extend(value)

    elif isinstance(
        google_data,
        list,
    ):
        footprints.extend(
            google_data
        )

    unique_footprints = []

    seen = set()

    for item in footprints:

        marker = str(item)

        if marker in seen:
            continue

        seen.add(marker)
        unique_footprints.append(item)

    scanners_available = list(
        results.keys()
    )

    return {
        "engine": {
            "id": "phoneinfoga",
            "name": "PhoneInfoga",
            "mode": "live",
        },

        "status": (
            "completed"
            if results
            else "no_results"
        ),

        "phone_number": number,

        "scanners_available": (
            scanners_available
        ),

        "scanner_results": results,

        "public_footprints": (
            unique_footprints
        ),

        "summary": {
            "scanners_returned": len(
                scanners_available
            ),
            "footprints_found": len(
                unique_footprints
            ),
        },
    }
