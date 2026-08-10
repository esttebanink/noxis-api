"""
NOXIS - PhoneInfoga Engine
Conector entre NOXIS API y el servicio PhoneInfoga desplegado en Render.
"""

from typing import Any, Dict, Optional
from urllib.parse import quote

import requests


PHONEINFOGA_BASE_URL = "https://noxis-phoneinfoga.onrender.com"


class PhoneInfogaEngine:
    """
    Motor de integración de PhoneInfoga para NOXIS.

    PhoneInfoga espera el número internacional SIN el signo "+" en
    las rutas /api/numbers/{number}/...
    """

    def __init__(
        self,
        base_url: str = PHONEINFOGA_BASE_URL,
        timeout: int = 60,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _prepare_number(self, phone_number: str) -> str:
        """
        Prepara el número para las rutas de PhoneInfoga.

        Ejemplo:
            +542932520063 -> 542932520063
        """

        if not phone_number:
            return ""

        number = str(phone_number).strip()

        # PhoneInfoga acepta el número internacional sin "+"
        number = number.lstrip("+")

        # Eliminamos caracteres habituales de presentación.
        number = (
            number.replace(" ", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
        )

        return number

    def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Ejecuta una petición contra PhoneInfoga.
        """

        url = f"{self.base_url}{endpoint}"

        try:
            response = requests.request(
                method=method,
                url=url,
                timeout=self.timeout,
                **kwargs,
            )

            response.raise_for_status()

            try:
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "data": response.json(),
                }

            except ValueError:
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "data": {
                        "raw": response.text
                    },
                }

        except requests.Timeout:
            return {
                "success": False,
                "error": "timeout",
                "message": "PhoneInfoga excedió el tiempo máximo de respuesta.",
                "url": url,
            }

        except requests.ConnectionError as exc:
            return {
                "success": False,
                "error": "connection_error",
                "message": "No fue posible conectar con PhoneInfoga.",
                "detail": str(exc),
                "url": url,
            }

        except requests.HTTPError as exc:
            status_code: Optional[int] = None
            response_text: Optional[str] = None

            if exc.response is not None:
                status_code = exc.response.status_code
                response_text = exc.response.text

            return {
                "success": False,
                "error": "http_error",
                "status_code": status_code,
                "message": "PhoneInfoga respondió con un error HTTP.",
                "detail": response_text or str(exc),
                "url": url,
            }

        except requests.RequestException as exc:
            return {
                "success": False,
                "error": "request_error",
                "message": "Error realizando la solicitud a PhoneInfoga.",
                "detail": str(exc),
                "url": url,
            }

        except Exception as exc:
            return {
                "success": False,
                "error": "unexpected_error",
                "message": "Se produjo un error inesperado en PhoneInfoga Engine.",
                "detail": str(exc),
                "url": url,
            }

    def health(self) -> Dict[str, Any]:
        """
        Comprueba si el servicio PhoneInfoga está disponible.
        """

        result = self._request(
            "GET",
            "/api/",
        )

        return {
            "engine": {
                "id": "phoneinfoga",
                "name": "PhoneInfoga",
                "mode": "live",
            },
            "service": {
                "url": self.base_url,
            },
            "result": result,
        }

    def validate(
        self,
        phone_number: str,
    ) -> Dict[str, Any]:
        """
        Valida el número utilizando PhoneInfoga.
        """

        clean_number = self._prepare_number(phone_number)

        if not clean_number:
            return {
                "success": False,
                "error": "empty_phone_number",
                "message": "No se proporcionó un número de teléfono.",
            }

        encoded_number = quote(
            clean_number,
            safe="",
        )

        return self._request(
            "GET",
            f"/api/numbers/{encoded_number}/validate",
        )

    def scan_local(
        self,
        phone_number: str,
    ) -> Dict[str, Any]:
        """
        Ejecuta el scanner local de PhoneInfoga.
        """

        clean_number = self._prepare_number(phone_number)

        if not clean_number:
            return {
                "success": False,
                "error": "empty_phone_number",
                "message": "No se proporcionó un número de teléfono.",
            }

        encoded_number = quote(
            clean_number,
            safe="",
        )

        return self._request(
            "GET",
            f"/api/numbers/{encoded_number}/scan/local",
        )

    def scan(
        self,
        phone_number: str,
        default_region: str = "AR",
    ) -> Dict[str, Any]:
        """
        Ejecuta el análisis principal de PhoneInfoga.

        NOXIS puede enviar:
            +542932520063

        PhoneInfoga recibirá:
            542932520063
        """

        original_number = phone_number
        clean_number = self._prepare_number(phone_number)

        if not clean_number:
            return {
                "status": "error",
                "phone_number": original_number,
                "default_region": default_region,
                "engine": {
                    "id": "phoneinfoga",
                    "name": "PhoneInfoga",
                    "mode": "live",
                },
                "error": "empty_phone_number",
                "message": "No se proporcionó un número de teléfono.",
            }

        validation = self.validate(original_number)

        # Si PhoneInfoga rechaza el número, no continuamos.
        if not validation.get("success"):
            return {
                "status": "error",
                "phone_number": original_number,
                "phoneinfoga_number": clean_number,
                "default_region": default_region,
                "engine": {
                    "id": "phoneinfoga",
                    "name": "PhoneInfoga",
                    "mode": "live",
                },
                "service": {
                    "url": self.base_url,
                },
                "validation": validation,
                "error": "phoneinfoga_validation_failed",
                "message": "PhoneInfoga no pudo validar el número.",
            }

        local_result = self.scan_local(original_number)

        completed = local_result.get("success", False)

        return {
            "status": "completed" if completed else "partial",
            "phone_number": original_number,
            "phoneinfoga_number": clean_number,
            "default_region": default_region,
            "engine": {
                "id": "phoneinfoga",
                "name": "PhoneInfoga",
                "mode": "live",
            },
            "service": {
                "url": self.base_url,
            },
            "validation": validation,
            "local": local_result,
        }


# Instancia reutilizable por NOXIS API
phoneinfoga_engine = PhoneInfogaEngine()


def search_phoneinfoga(
    phone_number: str,
    default_region: str = "AR",
) -> Dict[str, Any]:
    """
    Función pública para utilizar PhoneInfoga desde NOXIS.

    Ejemplo:
        search_phoneinfoga("+542932520063", "AR")
    """

    return phoneinfoga_engine.scan(
        phone_number=phone_number,
        default_region=default_region,
    )
