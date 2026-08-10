"""
NOXIS - PhoneInfoga Engine

Connector between NOXIS API and the PhoneInfoga service
deployed independently on Render.

PhoneInfoga service:
https://noxis-phoneinfoga.onrender.com
"""

from typing import Any, Dict
from urllib.parse import quote

import requests


PHONEINFOGA_BASE_URL = "https://noxis-phoneinfoga.onrender.com"


class PhoneInfogaEngine:
    """
    PhoneInfoga connector for NOXIS Phone Intelligence.

    NOXIS uses E.164 numbers such as:

        +542932520063

    PhoneInfoga API endpoints expect the international
    number without the leading "+" sign:

        542932520063
    """

    def __init__(
        self,
        base_url: str = PHONEINFOGA_BASE_URL,
        timeout: int = 60,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ============================================================
    # ENGINE INFORMATION
    # ============================================================

    def engine_info(self) -> Dict[str, Any]:
        return {
            "id": "phoneinfoga",
            "name": "PhoneInfoga",
            "mode": "live",
        }

    # ============================================================
    # NUMBER PREPARATION
    # ============================================================

    def _prepare_number(self, phone_number: str) -> str:
        """
        Convert a phone number into the format expected
        by the PhoneInfoga HTTP API.
        """

        if not phone_number:
            return ""

        number = str(phone_number).strip()

        number = (
            number
            .replace(" ", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
        )

        # PhoneInfoga endpoints expect the number without "+"
        number = number.lstrip("+")

        return number

    # ============================================================
    # HTTP REQUEST
    # ============================================================

    def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> Dict[str, Any]:

        url = f"{self.base_url}{endpoint}"

        try:
            response = requests.request(
                method=method,
                url=url,
                timeout=self.timeout,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "NOXIS-PhoneIntelligence/0.1",
                },
                **kwargs,
            )

            try:
                data = response.json()
            except ValueError:
                data = {
                    "raw": response.text
                }

            if response.status_code >= 400:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "url": url,
                    "data": data,
                }

            return {
                "success": True,
                "status_code": response.status_code,
                "url": url,
                "data": data,
            }

        except requests.Timeout:
            return {
                "success": False,
                "error": "timeout",
                "message": "PhoneInfoga request timed out.",
                "url": url,
            }

        except requests.ConnectionError as exc:
            return {
                "success": False,
                "error": "connection_error",
                "message": "Unable to connect to PhoneInfoga.",
                "detail": str(exc),
                "url": url,
            }

        except requests.RequestException as exc:
            return {
                "success": False,
                "error": "request_error",
                "message": "PhoneInfoga request failed.",
                "detail": str(exc),
                "url": url,
            }

        except Exception as exc:
            return {
                "success": False,
                "error": "unexpected_error",
                "message": "Unexpected PhoneInfoga Engine error.",
                "detail": str(exc),
                "url": url,
            }

    # ============================================================
    # HEALTH CHECK
    # ============================================================

    def health(self) -> Dict[str, Any]:
        """
        Check if the PhoneInfoga service is reachable.
        """

        result = self._request(
            "GET",
            "/api/",
        )

        return {
            "engine": self.engine_info(),
            "service": {
                "url": self.base_url,
            },
            "result": result,
        }

    # ============================================================
    # VALIDATION
    # ============================================================

    def validate(self, phone_number: str) -> Dict[str, Any]:
        """
        Validate the phone number using PhoneInfoga.
        """

        clean_number = self._prepare_number(phone_number)

        if not clean_number:
            return {
                "success": False,
                "error": "empty_phone_number",
                "message": "No phone number was provided.",
            }

        encoded_number = quote(
            clean_number,
            safe="",
        )

        endpoint = (
            f"/api/numbers/"
            f"{encoded_number}/validate"
        )

        return self._request(
            "GET",
            endpoint,
        )

    # ============================================================
    # LOCAL SCANNER
    # ============================================================

    def scan_local(self, phone_number: str) -> Dict[str, Any]:
        """
        Run PhoneInfoga local scanner.
        """

        clean_number = self._prepare_number(phone_number)

        if not clean_number:
            return {
                "success": False,
                "error": "empty_phone_number",
            }

        encoded_number = quote(
            clean_number,
            safe="",
        )

        endpoint = (
            f"/api/numbers/"
            f"{encoded_number}/scan/local"
        )

        return self._request(
            "GET",
            endpoint,
        )

    # ============================================================
    # GOOGLE SEARCH SCANNER
    # ============================================================

    def scan_google_search(
        self,
        phone_number: str,
    ) -> Dict[str, Any]:
        """
        Run PhoneInfoga Google Search scanner.
        """

        clean_number = self._prepare_number(phone_number)

        if not clean_number:
            return {
                "success": False,
                "error": "empty_phone_number",
            }

        encoded_number = quote(
            clean_number,
            safe="",
        )

        endpoint = (
            f"/api/numbers/"
            f"{encoded_number}/scan/googlesearch"
        )

        return self._request(
            "GET",
            endpoint,
        )

    # ============================================================
    # NUMVERIFY SCANNER
    # ============================================================

    def scan_numverify(
        self,
        phone_number: str,
    ) -> Dict[str, Any]:
        """
        Run PhoneInfoga Numverify scanner.
        """

        clean_number = self._prepare_number(phone_number)

        if not clean_number:
            return {
                "success": False,
                "error": "empty_phone_number",
            }

        encoded_number = quote(
            clean_number,
            safe="",
        )

        endpoint = (
            f"/api/numbers/"
            f"{encoded_number}/scan/numverify"
        )

        return self._request(
            "GET",
            endpoint,
        )

    # ============================================================
    # OVH SCANNER
    # ============================================================

    def scan_ovh(
        self,
        phone_number: str,
    ) -> Dict[str, Any]:
        """
        Run PhoneInfoga OVH scanner.
        """

        clean_number = self._prepare_number(phone_number)

        if not clean_number:
            return {
                "success": False,
                "error": "empty_phone_number",
            }

        encoded_number = quote(
            clean_number,
            safe="",
        )

        endpoint = (
            f"/api/numbers/"
            f"{encoded_number}/scan/ovh"
        )

        return self._request(
            "GET",
            endpoint,
        )

    # ============================================================
    # PUBLIC FOOTPRINT EXTRACTION
    # ============================================================

    def _extract_public_footprints(
        self,
        scanner_results: Dict[str, Any],
    ) -> list:
        """
        Extract possible public URLs/results from scanner responses.
        """

        footprints = []

        google_result = scanner_results.get(
            "google_search",
            {},
        )

        google_data = google_result.get("data")

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

        elif isinstance(google_data, list):

            footprints.extend(google_data)

        unique_footprints = []
        seen = set()

        for item in footprints:

            marker = str(item)

            if marker in seen:
                continue

            seen.add(marker)
            unique_footprints.append(item)

        return unique_footprints

    # ============================================================
    # MAIN SEARCH METHOD
    # ============================================================

    def search(
        self,
        phone_number: str,
        default_region: str = "AR",
    ) -> Dict[str, Any]:
        """
        Main PhoneInfoga method used by NOXIS.

        IMPORTANT:
        phone_engine.py expects this exact method:

            phoneinfoga_engine.search(...)
        """

        original_number = (
            str(phone_number).strip()
            if phone_number
            else ""
        )

        clean_number = self._prepare_number(
            original_number
        )

        if not clean_number:

            return {
                "status": "error",
                "phone_number": original_number,
                "default_region": default_region,
                "engine": self.engine_info(),
                "error": "empty_phone_number",
                "message": "No phone number was provided.",
            }

        # --------------------------------------------------------
        # PHONEINFOGA VALIDATION
        # --------------------------------------------------------

        validation = self.validate(
            original_number
        )

        if not validation.get("success"):

            return {
                "status": "error",
                "phone_number": original_number,
                "phoneinfoga_number": clean_number,
                "default_region": default_region,
                "engine": self.engine_info(),
                "service": {
                    "url": self.base_url,
                },
                "validation": validation,
                "error": "phoneinfoga_validation_failed",
                "message": (
                    "PhoneInfoga could not validate the phone number."
                ),
            }

        # --------------------------------------------------------
        # SCANNERS
        # --------------------------------------------------------

        scanner_results = {
            "local": self.scan_local(
                original_number
            ),
            "google_search": self.scan_google_search(
                original_number
            ),
            "numverify": self.scan_numverify(
                original_number
            ),
            "ovh": self.scan_ovh(
                original_number
            ),
        }

        available_scanners = []
        failed_scanners = []

        for scanner_name, scanner_result in scanner_results.items():

            if scanner_result.get("success"):
                available_scanners.append(
                    scanner_name
                )
            else:
                failed_scanners.append(
                    scanner_name
                )

        # --------------------------------------------------------
        # PUBLIC FOOTPRINTS
        # --------------------------------------------------------

        public_footprints = self._extract_public_footprints(
            scanner_results
        )

        # --------------------------------------------------------
        # FINAL STATUS
        # --------------------------------------------------------

        if available_scanners and not failed_scanners:
            status = "completed"

        elif available_scanners:
            status = "partial"

        else:
            status = "partial"

        # --------------------------------------------------------
        # RESPONSE
        # --------------------------------------------------------

        return {
            "status": status,

            "phone_number": original_number,

            "phoneinfoga_number": clean_number,

            "default_region": default_region,

            "engine": self.engine_info(),

            "service": {
                "url": self.base_url,
            },

            "validation": validation,

            "scanners": {
                "available": available_scanners,
                "failed": failed_scanners,
            },

            "scanner_results": scanner_results,

            "public_footprints": public_footprints,

            "summary": {
                "scanners_available": len(
                    available_scanners
                ),
                "scanners_failed": len(
                    failed_scanners
                ),
                "footprints_found": len(
                    public_footprints
                ),
            },
        }

    # ============================================================
    # SCAN ALIAS
    # ============================================================

    def scan(
        self,
        phone_number: str,
        default_region: str = "AR",
    ) -> Dict[str, Any]:
        """
        Compatibility alias.

        Both methods are intentionally available:

            search()
            scan()
        """

        return self.search(
            phone_number=phone_number,
            default_region=default_region,
        )


# ================================================================
# GLOBAL ENGINE INSTANCE
# ================================================================

phoneinfoga_engine = PhoneInfogaEngine()


# ================================================================
# PUBLIC FUNCTIONS
# ================================================================

def search_phoneinfoga(
    phone_number: str,
    default_region: str = "AR",
) -> Dict[str, Any]:
    """
    Public helper for NOXIS.
    """

    return phoneinfoga_engine.search(
        phone_number=phone_number,
        default_region=default_region,
    )


def scan_phoneinfoga(
    phone_number: str,
    default_region: str = "AR",
) -> Dict[str, Any]:
    """
    Alternative public helper.
    """

    return phoneinfoga_engine.scan(
        phone_number=phone_number,
        default_region=default_region,
    )


def phoneinfoga_health() -> Dict[str, Any]:
    """
    Public health-check helper.
    """

    return phoneinfoga_engine.health()
