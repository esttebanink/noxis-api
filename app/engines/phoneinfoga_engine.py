import os
from typing import Any, Dict, Optional

import requests


# ============================================================
# NOXIS - PHONEINFOGA ENGINE
# ============================================================
#
# Conector entre NOXIS API y el microservicio PhoneInfoga
# desplegado independientemente en Render.
#
# Servicio actual:
# https://noxis-phoneinfoga.onrender.com
#
# Puede sobrescribirse mediante la variable de entorno:
# PHONEINFOGA_URL
# ============================================================


DEFAULT_PHONEINFOGA_URL = "https://noxis-phoneinfoga.onrender.com"

PHONEINFOGA_URL = os.getenv(
    "PHONEINFOGA_URL",
    DEFAULT_PHONEINFOGA_URL,
).strip().rstrip("/")


class PhoneInfogaEngine:
    """
    Motor de integración de PhoneInfoga para NOXIS.

    Este módulo NO ejecuta PhoneInfoga localmente.

    Se comunica mediante HTTP con el microservicio
    noxis-phoneinfoga desplegado en Render y devuelve
    una respuesta normalizada para NOXIS.
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

    # ========================================================
    # INFORMACIÓN DEL MOTOR
    # ========================================================

    def engine_info(self) -> Dict[str, Any]:
        return {
            "id": self.ENGINE_ID,
            "name": self.ENGINE_NAME,
            "mode": "live",
            "service_url": self.base_url,
        }

    # ========================================================
    # HEALTH CHECK
    # ========================================================

    def health(self) -> Dict[str, Any]:
        """
        Comprueba si el servicio PhoneInfoga responde.

        Algunos despliegues no poseen /health, por lo que
        también se prueba la raíz del servicio.
        """

        endpoints = [
            "/health",
            "/",
        ]

        attempts = []

        for endpoint in endpoints:
            url = f"{self.base_url}{endpoint}"

            try:
                response = requests.get(
                    url,
                    timeout=15,
                )

                attempts.append({
                    "endpoint": endpoint,
                    "status_code": response.status_code,
                })

                if response.status_code < 500:
                    return {
                        "available": True,
                        "engine": self.engine_info(),
                        "endpoint": endpoint,
                        "status_code": response.status_code,
                    }

            except requests.RequestException as exc:
                attempts.append({
                    "endpoint": endpoint,
                    "error": str(exc),
                })

        return {
            "available": False,
            "engine": self.engine_info(),
            "attempts": attempts,
        }

    # ========================================================
    # BÚSQUEDA
    # ========================================================

    def search(
        self,
        phone_number: str,
        default_region: str = "AR",
    ) -> Dict[str, Any]:
        """
        Consulta PhoneInfoga utilizando un número de teléfono.

        Se prueban varios formatos de endpoint para permitir
        compatibilidad con distintas versiones/configuraciones
        del microservicio.
        """

        phone_number = self._normalize_input(phone_number)
        default_region = (default_region or "AR").strip().upper()

        if not phone_number:
            return self._error_response(
                phone_number="",
                default_region=default_region,
                error="phone_number_required",
                message="Debe proporcionar un número de teléfono.",
            )

        attempts = [
            {
                "method": "POST",
                "endpoint": "/api/v1/scan",
                "json": {
                    "phone_number": phone_number,
                    "default_region": default_region,
                },
            },
            {
                "method": "POST",
                "endpoint": "/scan",
                "json": {
                    "phone_number": phone_number,
                    "default_region": default_region,
                },
            },
            {
                "method": "POST",
                "endpoint": "/api/scan",
                "json": {
                    "phone_number": phone_number,
                    "default_region": default_region,
                },
            },
            {
                "method": "GET",
                "endpoint": "/api/v1/scan",
                "params": {
                    "number": phone_number,
                },
            },
            {
                "method": "GET",
                "endpoint": "/scan",
                "params": {
                    "number": phone_number,
                },
            },
            {
                "method": "GET",
                "endpoint": "/api/scan",
                "params": {
                    "number": phone_number,
                },
            },
        ]

        errors = []

        for attempt in attempts:

            endpoint = attempt["endpoint"]
            method = attempt["method"]

            url = f"{self.base_url}{endpoint}"

            try:

                if method == "POST":

                    response = requests.post(
                        url,
                        json=attempt.get("json"),
                        headers={
                            "Accept": "application/json",
                            "Content-Type": "application/json",
                        },
                        timeout=self.timeout,
                    )

                else:

                    response = requests.get(
                        url,
                        params=attempt.get("params"),
                        headers={
                            "Accept": "application/json",
                        },
                        timeout=self.timeout,
                    )

                # Endpoint inexistente.
                # Probamos automáticamente el siguiente.
                if response.status_code == 404:

                    errors.append({
                        "method": method,
                        "endpoint": endpoint,
                        "status_code": 404,
                    })

                    continue

                # Método incorrecto para ese endpoint.
                if response.status_code == 405:

                    errors.append({
                        "method": method,
                        "endpoint": endpoint,
                        "status_code": 405,
                    })

                    continue

                # Validación incompatible con ese endpoint.
                if response.status_code == 422:

                    errors.append({
                        "method": method,
                        "endpoint": endpoint,
                        "status_code": 422,
                        "response": self._safe_response(response),
                    })

                    continue

                response.raise_for_status()

                data = self._safe_response(response)

                return self._success_response(
                    phone_number=phone_number,
                    default_region=default_region,
                    endpoint=endpoint,
                    method=method,
                    data=data,
                )

            except requests.Timeout:

                errors.append({
                    "method": method,
                    "endpoint": endpoint,
                    "error": "timeout",
                })

            except requests.ConnectionError as exc:

                errors.append({
                    "method": method,
                    "endpoint": endpoint,
                    "error": "connection_error",
                    "detail": str(exc),
                })

            except requests.RequestException as exc:

                errors.append({
                    "method": method,
                    "endpoint": endpoint,
                    "error": "request_error",
                    "detail": str(exc),
                })

            except Exception as exc:

                errors.append({
                    "method": method,
                    "endpoint": endpoint,
                    "error": "unexpected_error",
                    "detail": str(exc),
                })

        return self._error_response(
            phone_number=phone_number,
            default_region=default_region,
            error="phoneinfoga_unavailable",
            message=(
                "No fue posible obtener resultados desde "
                "el servicio PhoneInfoga."
            ),
            attempts=errors,
        )

    # ========================================================
    # NORMALIZACIÓN
    # ========================================================

    def _normalize_input(self, phone_number: str) -> str:
        """
        Limpieza mínima.

        La normalización E.164 definitiva corresponde al
        Phone Intelligence Engine basado en libphonenumber.
        """

        if phone_number is None:
            return ""

        return str(phone_number).strip()

    # ========================================================
    # PARSEO SEGURO
    # ========================================================

    def _safe_response(
        self,
        response: requests.Response,
    ) -> Any:
        """
        Intenta devolver JSON.

        Si el servicio responde texto, devuelve el contenido
        sin provocar un error.
        """

        try:
            return response.json()

        except ValueError:
            return {
                "raw": response.text,
            }

    # ========================================================
    # RESPUESTA CORRECTA
    # ========================================================

    def _success_response(
        self,
        phone_number: str,
        default_region: str,
        endpoint: str,
        method: str,
        data: Any,
    ) -> Dict[str, Any]:

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
                "endpoint": endpoint,
                "method": method,
            },
            "results": data,
        }

    # ========================================================
    # RESPUESTA DE ERROR
    # ========================================================

    def _error_response(
        self,
        phone_number: str,
        default_region: str,
        error: str,
        message: str,
        attempts: Optional[list] = None,
    ) -> Dict[str, Any]:

        response = {
            "status": "error",
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
            "error": error,
            "message": message,
        }

        if attempts is not None:
            response["attempts"] = attempts

        return response


# ============================================================
# FUNCIÓN SIMPLE PARA NOXIS
# ============================================================

def search_phoneinfoga(
    phone_number: str,
    default_region: str = "AR",
) -> Dict[str, Any]:
    """
    Punto de entrada simplificado.

    Permite utilizar:

        from app.engines.phoneinfoga_engine import search_phoneinfoga

        result = search_phoneinfoga("+542932520063", "AR")
    """

    engine = PhoneInfogaEngine()

    return engine.search(
        phone_number=phone_number,
        default_region=default_region,
    )


# ============================================================
# HEALTH CHECK SIMPLE
# ============================================================

def phoneinfoga_health() -> Dict[str, Any]:
    engine = PhoneInfogaEngine()

    return engine.health()
