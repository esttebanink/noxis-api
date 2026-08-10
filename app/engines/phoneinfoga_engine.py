import os
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests


DEFAULT_PHONEINFOGA_URL = "https://noxis-phoneinfoga.onrender.com"

PHONEINFOGA_URL = os.getenv(
    "PHONEINFOGA_URL",
    DEFAULT_PHONEINFOGA_URL,
).strip().rstrip("/")


class PhoneInfogaEngine:
    """
    Conector entre NOXIS API y el microservicio PhoneInfoga.
    """

    ENGINE_ID = "phoneinfoga"
    ENGINE_NAME = "PhoneInfoga"

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: int = 60,
    ):
        self.base_url = (
            base_url
            or PHONEINFOGA_URL
            or DEFAULT_PHONEINFOGA_URL
        ).strip().rstrip("/")

        self.timeout = timeout

    def engine_info(self) -> Dict[str, Any]:
        return {
            "id": self.ENGINE_ID,
            "name": self.ENGINE_NAME,
            "mode": "live",
            "service_url": self.base_url,
        }

    def health(self) -> Dict[str, Any]:
        """
        PhoneInfoga expone /api/ como health endpoint.
        """

        try:
            response = requests.get(
                f"{self.base_url}/api/",
                timeout=15,
            )

            return {
                "available": response.status_code < 500,
                "status_code": response.status_code,
                "engine": self.engine_info(),
            }

        except requests.RequestException as exc:
            return {
                "available": False,
                "engine": self.engine_info(),
                "error": str(exc),
            }

    def _safe_response(
        self,
        response: requests.Response,
    ) -> Any:

        try:
            return response.json()

        except ValueError:
            return {
                "raw": response.text,
            }

    def _call_endpoint(
        self,
        endpoint: str,
    ) -> Dict[str, Any]:

        url = f"{self.base_url}{endpoint}"

        try:
            response = requests.get(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "NOXIS-PhoneIntelligence",
                },
                timeout=self.timeout,
            )

            data = self._safe_response(response)

            return {
                "success": response.status_code < 400,
                "status_code": response.status_code,
                "endpoint": endpoint,
                "data": data,
            }

        except requests.Timeout:
            return {
                "success": False,
                "endpoint": endpoint,
                "error": "timeout",
            }

        except requests.RequestException as exc:
            return {
                "success": False,
                "endpoint": endpoint,
                "error": "request_error",
                "detail": str(exc),
            }

    def search(
        self,
        phone_number: str,
        default_region: str = "AR",
    ) -> Dict[str, Any]:

        phone_number = (phone_number or "").strip()

        if not phone_number:
            return {
                "status": "error",
                "engine": self.engine_info(),
                "error": "phone_number_required",
                "message": "Debe proporcionar un número de teléfono.",
            }

        encoded_number = quote(
            phone_number,
            safe="",
        )

        endpoints = {
            "validation": (
                f"/api/numbers/{encoded_number}/validate"
            ),
            "local": (
                f"/api/numbers/{encoded_number}/scan/local"
            ),
            "google_search": (
                f"/api/numbers/{encoded_number}/scan/googlesearch"
            ),
            "numverify": (
                f"/api/numbers/{encoded_number}/scan/numverify"
            ),
            "ovh": (
                f"/api/numbers/{encoded_number}/scan/ovh"
            ),
        }

        scanner_results: Dict[str, Any] = {}
        available_scanners = []
        failed_scanners = []

        for scanner_name, endpoint in endpoints.items():

            result = self._call_endpoint(
                endpoint
            )

            scanner_results[scanner_name] = result

            if result.get("success"):
                available_scanners.append(
                    scanner_name
                )
            else:
                failed_scanners.append(
                    scanner_name
                )

        footprints = []

        google_result = scanner_results.get(
            "google_search",
            {}
        )

        google_data = google_result.get(
            "data"
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
            list
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

        return {
            "status": "completed",

            "phone_number": phone_number,

            "default_region": default_region,

            "engine": {
                "id": self.ENGINE_ID,
                "name": self.ENGINE_NAME,
                "mode": "live",
            },

            "service": {
                "url": self.base_url,
            },

            "scanners": {
                "available": available_scanners,
                "failed": failed_scanners,
            },

            "scanner_results": scanner_results,

            "public_footprints": unique_footprints,

            "summary": {
                "scanners_available": len(
                    available_scanners
                ),
                "scanners_failed": len(
                    failed_scanners
                ),
                "footprints_found": len(
                    unique_footprints
                ),
            },
        }


def search_phoneinfoga(
    phone_number: str,
    default_region: str = "AR",
) -> Dict[str, Any]:

    engine = PhoneInfogaEngine()

    return engine.search(
        phone_number=phone_number,
        default_region=default_region,
    )


def phoneinfoga_health() -> Dict[str, Any]:

    engine = PhoneInfogaEngine()

    return engine.health()
