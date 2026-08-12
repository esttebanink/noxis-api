"""
NOXIS - Holehe Engine
=====================

Motor de integración entre NOXIS API y el microservicio
NOXIS Holehe.

Responsabilidades:
- Consultar noxis-holehe.
- Despertar el servicio cuando Render Free está suspendido.
- Ejecutar Email Intelligence.
- Normalizar la respuesta.
- Mantener separados:
    * presencia técnica
    * evidencia adicional
    * identidad confirmada

Una coincidencia de Holehe NO confirma identidad personal.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import requests


class HoleheEngine:

    ENGINE_ID = "holehe"
    ENGINE_NAME = "Holehe"

    DEFAULT_BASE_URL = (
        "https://noxis-holehe.onrender.com"
    )

    # ========================================================
    # RENDER FREE / COLD START
    # ========================================================

    DEFAULT_TIMEOUT = 45
    DEFAULT_RETRIES = 6
    DEFAULT_RETRY_DELAY = 5

    # Después de agotar los reintentos normales,
    # esperamos una vez más y realizamos una comprobación final.
    FINAL_WAKE_DELAY = 12

    RETRYABLE_STATUS_CODES = {
        408,
        425,
        429,
        500,
        502,
        503,
        504,
    }

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:

        configured_url = (
            base_url
            or os.getenv("HOLEHE_URL")
            or self.DEFAULT_BASE_URL
        )

        self.base_url = configured_url.rstrip("/")

        try:
            self.timeout = int(
                timeout
                or os.getenv("HOLEHE_TIMEOUT")
                or self.DEFAULT_TIMEOUT
            )
        except (TypeError, ValueError):
            self.timeout = self.DEFAULT_TIMEOUT

        try:
            self.retries = int(
                os.getenv(
                    "HOLEHE_RETRIES",
                    str(self.DEFAULT_RETRIES),
                )
            )
        except (TypeError, ValueError):
            self.retries = self.DEFAULT_RETRIES

        try:
            self.retry_delay = float(
                os.getenv(
                    "HOLEHE_RETRY_DELAY",
                    str(self.DEFAULT_RETRY_DELAY),
                )
            )
        except (TypeError, ValueError):
            self.retry_delay = (
                self.DEFAULT_RETRY_DELAY
            )

        try:
            self.final_wake_delay = float(
                os.getenv(
                    "HOLEHE_FINAL_WAKE_DELAY",
                    str(self.FINAL_WAKE_DELAY),
                )
            )
        except (TypeError, ValueError):
            self.final_wake_delay = (
                self.FINAL_WAKE_DELAY
            )

        self.session = requests.Session()

        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": (
                    "NOXIS/0.5 EmailIntelligence"
                ),
                "Connection": "keep-alive",
            }
        )

    # ========================================================
    # UTILIDADES
    # ========================================================

    def _normalize_email(
        self,
        email: str,
    ) -> str:

        if email is None:
            return ""

        return str(email).strip().lower()

    def _safe_response_data(
        self,
        response: requests.Response,
    ) -> Dict[str, Any]:

        try:

            data = response.json()

            if isinstance(data, dict):
                return data

            return {
                "value": data
            }

        except ValueError:

            text = response.text or ""

            if len(text) > 2000:
                text = (
                    text[:2000]
                    + "...[truncated]"
                )

            return {
                "raw": text
            }

    # ========================================================
    # HTTP
    # ========================================================

    def _request(
        self,
        method: str,
        endpoint: str,
        retries: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:

        url = f"{self.base_url}{endpoint}"

        max_retries = (
            self.retries
            if retries is None
            else retries
        )

        if max_retries < 1:
            max_retries = 1

        attempts: List[Dict[str, Any]] = []

        for attempt in range(
            1,
            max_retries + 1,
        ):

            try:

                response = self.session.request(
                    method=method,
                    url=url,
                    timeout=self.timeout,
                    **kwargs,
                )

                data = self._safe_response_data(
                    response
                )

                attempts.append(
                    {
                        "attempt": attempt,
                        "status_code": (
                            response.status_code
                        ),
                    }
                )

                if response.ok:

                    return {
                        "success": True,
                        "status_code": (
                            response.status_code
                        ),
                        "url": url,
                        "attempts_count": attempt,
                        "data": data,
                        "attempts": attempts,
                    }

                if (
                    response.status_code
                    not in self.RETRYABLE_STATUS_CODES
                ):

                    return {
                        "success": False,
                        "status_code": (
                            response.status_code
                        ),
                        "url": url,
                        "attempts_count": attempt,
                        "data": data,
                        "error": "http_error",
                        "attempts": attempts,
                    }

                if attempt < max_retries:

                    time.sleep(
                        self.retry_delay
                        * attempt
                    )

                    continue

                return {
                    "success": False,
                    "status_code": (
                        response.status_code
                    ),
                    "url": url,
                    "attempts_count": attempt,
                    "data": data,
                    "error": (
                        "service_unavailable"
                    ),
                    "attempts": attempts,
                }

            except requests.Timeout as exc:

                attempts.append(
                    {
                        "attempt": attempt,
                        "error": "timeout",
                    }
                )

                if attempt < max_retries:

                    time.sleep(
                        self.retry_delay
                        * attempt
                    )

                    continue

                return {
                    "success": False,
                    "status_code": None,
                    "url": url,
                    "error": "timeout",
                    "detail": str(exc),
                    "attempts_count": attempt,
                    "attempts": attempts,
                }

            except requests.RequestException as exc:

                attempts.append(
                    {
                        "attempt": attempt,
                        "error": "request_error",
                    }
                )

                if attempt < max_retries:

                    time.sleep(
                        self.retry_delay
                        * attempt
                    )

                    continue

                return {
                    "success": False,
                    "status_code": None,
                    "url": url,
                    "error": "request_error",
                    "detail": str(exc),
                    "attempts_count": attempt,
                    "attempts": attempts,
                }

            except Exception as exc:

                return {
                    "success": False,
                    "status_code": None,
                    "url": url,
                    "error": "unexpected_error",
                    "detail": str(exc),
                    "attempts_count": attempt,
                    "attempts": attempts,
                }

        return {
            "success": False,
            "status_code": None,
            "url": url,
            "error": "unknown_request_error",
            "attempts": attempts,
        }

    # ========================================================
    # WAKE / HEALTH
    # ========================================================

    def wake_service(
        self,
    ) -> Dict[str, Any]:

        # ----------------------------------------------------
        # 1. Intentos normales con backoff progresivo
        # ----------------------------------------------------

        result = self._request(
            "GET",
            "/health",
            retries=self.retries,
        )

        if result.get("success"):

            result["service_alive"] = True
            result["final_probe_used"] = False

            return result

        # ----------------------------------------------------
        # 2. Última espera para cubrir el caso en que Render
        #    termina de arrancar justo después del último 502.
        # ----------------------------------------------------

        time.sleep(
            self.final_wake_delay
        )

        # ----------------------------------------------------
        # 3. Comprobación final, una sola vez
        # ----------------------------------------------------

        final_probe = self._request(
            "GET",
            "/health",
            retries=1,
        )

        if final_probe.get("success"):

            return {
                "success": True,

                "status_code": final_probe.get(
                    "status_code"
                ),

                "url": final_probe.get(
                    "url"
                ),

                "attempts_count": (
                    int(
                        result.get(
                            "attempts_count",
                            self.retries,
                        )
                        or self.retries
                    )
                    + 1
                ),

                "data": final_probe.get(
                    "data",
                    {},
                ),

                "attempts": (
                    result.get(
                        "attempts",
                        [],
                    )
                    + [
                        {
                            "attempt": "final_probe",
                            "status_code": (
                                final_probe.get(
                                    "status_code"
                                )
                            ),
                        }
                    ]
                ),

                "service_alive": True,

                "final_probe_used": True,

                "previous_error": result.get(
                    "error"
                ),
            }

        # ----------------------------------------------------
        # 4. Fallo definitivo
        # ----------------------------------------------------

        result["service_alive"] = False
        result["final_probe_used"] = True

        result["final_probe"] = {
            "success": final_probe.get(
                "success",
                False,
            ),

            "status_code": final_probe.get(
                "status_code"
            ),

            "error": final_probe.get(
                "error"
            ),

            "detail": final_probe.get(
                "detail"
            ),
        }

        return result

    def health(
        self,
    ) -> Dict[str, Any]:

        result = self.wake_service()

        data = result.get(
            "data",
            {},
        )

        if not isinstance(data, dict):
            data = {}

        return {
            "engine": {
                "id": self.ENGINE_ID,
                "name": self.ENGINE_NAME,
                "mode": "live",
            },

            "service": {
                "url": self.base_url,
            },

            "available": result.get(
                "success",
                False,
            ),

            "modules_loaded": data.get(
                "modules_loaded"
            ),

            "response": result,
        }

    # ========================================================
    # NORMALIZACIÓN DE RESULTADOS
    # ========================================================

    def _normalize_registered_accounts(
        self,
        accounts: Any,
    ) -> List[Dict[str, Any]]:

        if not isinstance(accounts, list):
            return []

        normalized: List[
            Dict[str, Any]
        ] = []

        for account in accounts:

            if not isinstance(
                account,
                dict,
            ):
                continue

            normalized.append(
                {
                    "source": (
                        account.get("site")
                        or "Unknown"
                    ),

                    "status": (
                        account.get("status")
                        or "registered"
                    ),

                    "exists": account.get(
                        "exists"
                    ),

                    "rate_limited": (
                        account.get(
                            "rate_limited",
                            False,
                        )
                    ),

                    "email_recovery": (
                        account.get(
                            "email_recovery"
                        )
                    ),

                    "phone_recovery": (
                        account.get(
                            "phone_recovery"
                        )
                    ),

                    "others": account.get(
                        "others"
                    ),

                    "technical_match": True,

                    "identity_confirmed": False,

                    "engine": self.ENGINE_ID,
                }
            )

        return normalized

    # ========================================================
    # BÚSQUEDA PRINCIPAL
    # ========================================================

    def search(
        self,
        email: str,
    ) -> Dict[str, Any]:

        normalized_email = (
            self._normalize_email(
                email
            )
        )

        if not normalized_email:

            return {
                "status": "error",

                "email": email,

                "engine": {
                    "id": self.ENGINE_ID,
                    "name": self.ENGINE_NAME,
                    "mode": "live",
                },

                "error": "invalid_email",

                "message": (
                    "El correo electrónico "
                    "está vacío."
                ),

                "registered_accounts": [],
            }

        # ====================================================
        # WAKE
        # ====================================================

        wakeup = self.wake_service()

        if not wakeup.get(
            "success"
        ):

            return {
                "status": "error",

                "email": normalized_email,

                "engine": {
                    "id": self.ENGINE_ID,
                    "name": self.ENGINE_NAME,
                    "mode": "live",
                },

                "service": {
                    "url": self.base_url,
                },

                "error": "holehe_unavailable",

                "message": (
                    "Holehe no respondió "
                    "después de varios intentos "
                    "y una comprobación final."
                ),

                "wakeup": wakeup,

                "summary": {
                    "modules_loaded": 0,
                    "sites_checked": 0,
                    "registered": 0,
                    "not_registered": 0,
                    "rate_limited": 0,
                    "unknown": 0,
                    "errors": 0,
                },

                "registered_accounts": [],

                "results": [],

                "evidence": {
                    "account_presence": {
                        "status": "unavailable",
                        "count": 0,
                        "technical_match": False,
                        "identity_confirmed": False,
                    }
                },
            }

        # ====================================================
        # SEARCH
        # ====================================================
        #
        # El servicio ya respondió /health.
        # La búsqueda completa se ejecuta UNA sola vez.
        # ====================================================

        response = self._request(
            "POST",
            "/api/v1/search/email",
            retries=1,
            json={
                "email": normalized_email
            },
        )

        if not response.get(
            "success"
        ):

            return {
                "status": "error",

                "email": normalized_email,

                "engine": {
                    "id": self.ENGINE_ID,
                    "name": self.ENGINE_NAME,
                    "mode": "live",
                },

                "service": {
                    "url": self.base_url,
                },

                "error": "holehe_search_failed",

                "message": (
                    "Holehe respondió al health check, "
                    "pero no fue posible completar "
                    "la búsqueda de email."
                ),

                "response": response,

                "wakeup": wakeup,

                "summary": {
                    "modules_loaded": 0,
                    "sites_checked": 0,
                    "registered": 0,
                    "not_registered": 0,
                    "rate_limited": 0,
                    "unknown": 0,
                    "errors": 0,
                },

                "registered_accounts": [],

                "results": [],

                "evidence": {
                    "account_presence": {
                        "status": "unavailable",
                        "count": 0,
                        "technical_match": False,
                        "identity_confirmed": False,
                    }
                },
            }

        data = response.get(
            "data",
            {},
        )

        if not isinstance(
            data,
            dict,
        ):
            data = {}

        # ====================================================
        # RESULTADOS
        # ====================================================

        raw_registered = data.get(
            "registered_accounts",
            [],
        )

        registered_accounts = (
            self._normalize_registered_accounts(
                raw_registered
            )
        )

        summary = data.get(
            "summary",
            {},
        )

        if not isinstance(
            summary,
            dict,
        ):
            summary = {}

        remote_status = data.get(
            "status",
            "completed",
        )

        # ====================================================
        # RESPONSE NOXIS
        # ====================================================

        return {
            "status": remote_status,

            "email": normalized_email,

            "engine": {
                "id": self.ENGINE_ID,
                "name": self.ENGINE_NAME,
                "mode": "live",
            },

            "service": {
                "url": self.base_url,
            },

            "duration_seconds": data.get(
                "duration_seconds"
            ),

            "summary": summary,

            "registered_accounts": (
                registered_accounts
            ),

            "results": data.get(
                "results",
                [],
            ),

            "evidence": {
                "account_presence": {
                    "status": (
                        "available"
                        if registered_accounts
                        else "none"
                    ),

                    "count": len(
                        registered_accounts
                    ),

                    "technical_match": bool(
                        registered_accounts
                    ),

                    "identity_confirmed": False,

                    "description": (
                        "Holehe detectó presencia "
                        "técnica del correo en "
                        "servicios externos. "
                        "Esto no confirma identidad."
                    ),
                }
            },

            "wakeup": {
                "success": True,

                "status_code": wakeup.get(
                    "status_code"
                ),

                "attempts_count": wakeup.get(
                    "attempts_count",
                    1,
                ),

                "final_probe_used": wakeup.get(
                    "final_probe_used",
                    False,
                ),
            },
        }

    # ========================================================
    # ALIAS
    # ========================================================

    def scan(
        self,
        email: str,
    ) -> Dict[str, Any]:

        return self.search(
            email=email
        )


# ============================================================
# INSTANCIA GLOBAL
# ============================================================

holehe_engine = HoleheEngine()


# ============================================================
# COMPATIBILIDAD
# ============================================================

def search_holehe(
    email: str,
) -> Dict[str, Any]:

    return holehe_engine.search(
        email=email
    )


def scan_holehe(
    email: str,
) -> Dict[str, Any]:

    return holehe_engine.search(
        email=email
    )
