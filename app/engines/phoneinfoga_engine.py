"""
NOXIS - PhoneInfoga Engine

Conector entre NOXIS API y el servicio PhoneInfoga
desplegado como microservicio independiente en Render.
"""

from typing import Any, Dict, Optional
from urllib.parse import quote

import requests


PHONEINFOGA_BASE_URL = "https://noxis-phoneinfoga.onrender.com"


class PhoneInfogaEngine:
    """
    Motor PhoneInfoga utilizado por NOXIS.

    NOXIS conserva los números en formato E.164:

        +542932520063

    Pero PhoneInfoga utiliza el número internacional
    sin el signo "+" dentro de sus endpoints:

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
    # INFORMACIÓN DEL MOTOR
    # ============================================================

    def engine_info(self) -> Dict[str, Any]:
        return {
            "id": "phoneinfoga",
            "name": "PhoneInfoga",
            "mode": "live",
        }

    # ============================================================
    # NORMALIZACIÓN PARA PHONEINFOGA
    # ============================================================

    def _prepare_number(
        self,
        phone_number: str,
    ) -> str:

        if not phone_number:
            return ""

        number = str(phone_number).strip()

        # PhoneInfoga espera el número internacional sin "+"
        number = number.lstrip("+")

        # Limpieza básica
        number = (
            number
            .replace(" ", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
        )

        return number

    # ============================================================
    # PETICIONES HTTP
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
                    "User-Agent": "NOXIS-PhoneIntelligence",
                },
                **kwargs,
            )

            status_code = response.status_code

            try:
                data = response.json()

            except ValueError:
                data = {
                    "raw": response.text
                }

            if status_code >= 400:

                return {
                    "success": False,
                    "status_code": status_code,
                    "url": url,
                    "data": data,
                }

            return {
                "success": True,
                "status_code": status_code,
                "url": url,
                "data": data,
            }

        except requests.Timeout:

            return {
                "success": False,
                "error": "timeout",
                "message": (
                    "PhoneInfoga excedió el tiempo máximo "
                    "de respuesta."
                ),
                "url": url,
            }

        except requests.ConnectionError as exc:

            return {
                "success": False,
                "error": "connection_error",
                "message": (
                    "No fue posible conectar con PhoneInfoga."
                ),
                "detail": str(exc),
                "url": url,
            }

        except requests.RequestException as exc:

            return {
                "success": False,
                "error": "request_error",
                "message": (
                    "Error realizando la solicitud a PhoneInfoga."
                ),
                "detail": str(exc),
                "url": url,
            }

        except Exception as exc:

            return {
                "success": False,
                "error": "unexpected_error",
                "message": (
                    "Se produjo un error inesperado "
                    "en PhoneInfoga Engine."
                ),
                "detail": str(exc),
                "url": url,
            }

    # ============================================================
    # HEALTH CHECK
    # ============================================================

    def health(self) -> Dict[str, Any]:

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
    # VALIDACIÓN
    # ============================================================

    def validate(
        self,
        phone_number: str,
    ) -> Dict[str, Any]:

        clean_number = self._prepare_number(
            phone_number
        )

        if not clean_number:

            return {
                "success": False,
                "error": "empty_phone_number",
                "message": (
                    "No se proporcionó un número de teléfono."
                ),
            }

        encoded_number = quote(
            clean_number,
            safe="",
        )

        return self._request(
            "GET",
            (
                f"/api/numbers/"
                f"{encoded_number}/validate"
            ),
        )

    # ============================================================
    # SCANNER LOCAL
    # ============================================================

    def scan_local(
        self,
        phone_number: str,
    ) -> Dict[str, Any]:

        clean_number = self._prepare_number(
            phone_number
        )

        if not clean_number:

            return {
                "success": False,
                "error": "empty_phone_number",
            }

        encoded_number = quote(
            clean_number,
            safe="",
        )

        return self._request(
            "GET",
            (
                f"/api/numbers/"
                f"{encoded_number}/scan/local"
            ),
        )

    # ============================================================
    # SCANNERS OPCIONALES
    # ============================================================

    def scan_google_search(
        self,
        phone_number: str,
    ) -> Dict[str, Any]:

        clean_number = self._prepare_number(
            phone_number
        )

        encoded_number = quote(
            clean_number,
            safe="",
        )

        return self._request(
            "GET",
            (
                f"/api/numbers/"
                f"{encoded_number}/scan/googlesearch"
            ),
        )

    def scan_numverify(
        self,
        phone_number: str,
    ) -> Dict[str, Any]:

        clean_number = self._prepare_number(
            phone_number
        )

        encoded_number = quote(
            clean_number,
            safe="",
        )

        return self._request(
            "GET",
            (
                f"/api/numbers/"
                f"{encoded_number}/scan/numverify"
            ),
        )

    def scan_ovh(
        self,
        phone_number: str,
    ) -> Dict[str, Any]:

        clean_number = self._prepare_number(
            phone_number
        )

        encoded_number = quote(
            clean_number,
            safe="",
        )

        return self._request(
            "GET",
            (
                f"/api/numbers/"
                f"{encoded_number}/scan/ovh"
            ),
        )

    # ============================================================
    # BÚSQUEDA PRINCIPAL
    # ============================================================

    def search(
        self,
        phone_number: str,
        default_region: str = "AR",
    ) -> Dict[str, Any]:
        """
        Método utilizado por phone_engine.py.

        IMPORTANTE:
        este método debe llamarse search porque NOXIS actualmente
        utiliza:

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
                "message": (
                    "No se proporcionó un número de teléfono."
                ),
            }

        # --------------------------------------------------------
        # VALIDACIÓN
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
                "error": (
                    "phoneinfoga_validation_failed"
                ),
                "message": (
                    "PhoneInfoga no pudo validar el número."
                ),
            }

        # --------------------------------------------------------
        # SCANNERS
        # --------------------------------------------------------

        scanner_results = {}

        scanner_results["local"] = (
            self.scan_local(
                original_number
            )
        )

        scanner_results["google_search"] = (
            self.scan_google_search(
                original_number
            )
        )

        scanner_results["numverify"] = (
            self.scan_numverify(
                original_number
            )
        )

        scanner_results["ovh"] = (
            self.scan_ovh(
                original_number
            )
        )

        available = []
        failed = []

        for scanner_name, scanner_result in (
            scanner_results.items()
        ):

            if scanner_result.get("success"):

                available.append(
                    scanner_name
                )

            else:

                failed.append(
                    scanner_name
                )

        # --------------------------------------------------------
        # HUELLAS PÚBLICAS
        # --------------------------------------------------------

        public_footprints = []

        google_result = scanner_results.get(
            "google_search",
            {}
        )

        google_data = google_result.get(
            "data"
        )

        if isinstance(
            google_data,
            dict,
        ):

            for key in (
                "results",
                "links",
                "urls",
                "footprints",
            ):

                value = google_data.get(
                    key
                )

                if isinstance(
                    value,
                    list,
                ):

                    public_footprints.extend(
                        value
                    )

        elif isinstance(
            google_data,
            list,
        ):

            public_footprints.extend(
                google_data
            )

        # Eliminar duplicados
        unique_footprints = []
        seen = set()

        for item in public_footprints:

            marker = str(item)

            if marker in seen:
                continue

            seen.add(marker)

            unique_footprints.append(
                item
            )

        # --------------------------------------------------------
        # STATUS REAL
        # --------------------------------------------------------

        if available:

            if failed:
                status = "partial"
            else:
                status = "completed"

        else:
            status = "partial"

        # --------------------------------------------------------
        # RESPUESTA
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
                "available": available,
                "failed": failed,
            },

            "scanner_results": (
                scanner_results
            ),

            "public_footprints": (
                unique_footprints
            ),

            "summary": {
                "scanners_available": len(
                    available
                ),
                "scanners_failed": len(
                    failed
                ),
                "footprints_found": len(
                    unique_footprints
                ),
            },
        }

    # ============================================================
    # ALIAS SCAN
    # ============================================================

    def scan(
        self,
        phone_number: str,
        default_region: str = "AR",
    ) -> Dict[str, Any]:
        """
        Alias adicional para compatibilidad futura.
        """

        return self.search(
            phone_number=phone_number,
            default_region=default_region,
        )


# ================================================================
# INSTANCIA GLOBAL
# ================================================================

phoneinfoga_engine = PhoneInfogaEngine()


# ================================================================
# FUNCIONES PÚBLICAS
# ================================================================

def search_phoneinfoga(
    phone_number: str,
    default_region: str = "AR",
) -> Dict[str, Any]:

    return phoneinfoga_engine.search(
        phone_number=phone_number,
        default_region=default_region,
    )


def phoneinfoga_health() -> Dict[str, Any]:

    return phoneinfoga_engine.health()
