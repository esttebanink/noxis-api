"""
NOXIS - PhoneInfoga Engine
==========================

Motor de integración entre NOXIS API y PhoneInfoga.

Objetivos:
- Validar números mediante PhoneInfoga
- Ejecutar scanners disponibles
- Procesar Google Search
- Convertir dorks en footprints para NOXIS
- Tolerar fallos parciales
- Recuperarse automáticamente de cold starts de Render
- No confundir búsquedas sugeridas con coincidencias confirmadas
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests


class PhoneInfogaEngine:

    ENGINE_ID = "phoneinfoga"
    ENGINE_NAME = "PhoneInfoga"

    DEFAULT_BASE_URL = "https://noxis-phoneinfoga.onrender.com"

    DEFAULT_TIMEOUT = 35
    DEFAULT_RETRIES = 4
    DEFAULT_RETRY_DELAY = 5

    RETRYABLE_STATUS_CODES = {
        408,
        425,
        429,
        500,
        502,
        503,
        504,
    }

    SCANNERS = (
        "local",
        "googlesearch",
        "numverify",
        "ovh",
    )

    CATEGORY_MAP = {
        "social_media": {
            "label": "Redes sociales",
            "type": "social_media",
            "priority": 1,
        },
        "reputation": {
            "label": "Reputación",
            "type": "reputation",
            "priority": 2,
        },
        "individuals": {
            "label": "Personas y directorios",
            "type": "individuals",
            "priority": 3,
        },
        "general": {
            "label": "Búsqueda general",
            "type": "general",
            "priority": 4,
        },
        "disposable_providers": {
            "label": "Proveedores temporales",
            "type": "disposable_providers",
            "priority": 5,
        },
    }

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:

        configured_url = (
            base_url
            or os.getenv("PHONEINFOGA_URL")
            or self.DEFAULT_BASE_URL
        )

        self.base_url = configured_url.rstrip("/")

        try:
            self.timeout = int(
                timeout
                or os.getenv("PHONEINFOGA_TIMEOUT")
                or self.DEFAULT_TIMEOUT
            )
        except (TypeError, ValueError):
            self.timeout = self.DEFAULT_TIMEOUT

        try:
            self.retries = int(
                os.getenv(
                    "PHONEINFOGA_RETRIES",
                    str(self.DEFAULT_RETRIES),
                )
            )
        except (TypeError, ValueError):
            self.retries = self.DEFAULT_RETRIES

        try:
            self.retry_delay = float(
                os.getenv(
                    "PHONEINFOGA_RETRY_DELAY",
                    str(self.DEFAULT_RETRY_DELAY),
                )
            )
        except (TypeError, ValueError):
            self.retry_delay = self.DEFAULT_RETRY_DELAY

        self.session = requests.Session()

        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "NOXIS/0.3 PhoneIntelligence",
                "Connection": "keep-alive",
            }
        )

    # ============================================================
    # UTILIDADES
    # ============================================================

    def _prepare_number(
        self,
        phone_number: str,
    ) -> str:

        if phone_number is None:
            return ""

        raw = str(phone_number).strip()

        return "".join(
            char
            for char in raw
            if char.isdigit()
        )

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

            # Evitamos devolver páginas HTML gigantes
            # de Render dentro de la respuesta de NOXIS.
            if len(text) > 2000:
                text = text[:2000] + "...[truncated]"

            return {
                "raw": text
            }

    # ============================================================
    # REQUEST CON RETRIES
    # ============================================================

    def _request(
        self,
        method: str,
        endpoint: str,
        retries: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:

        """
        Ejecuta una petición segura contra PhoneInfoga.

        Implementa:
        - retries automáticos
        - tolerancia a 502/503/504
        - backoff progresivo
        - protección ante timeout
        - nunca propaga excepciones hacia NOXIS
        """

        url = f"{self.base_url}{endpoint}"

        max_retries = (
            self.retries
            if retries is None
            else retries
        )

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

                attempt_info = {
                    "attempt": attempt,
                    "status_code": response.status_code,
                }

                attempts.append(
                    attempt_info
                )

                if response.ok:

                    return {
                        "success": True,
                        "status_code": response.status_code,
                        "url": url,
                        "attempts_count": attempt,
                        "data": data,
                    }

                if (
                    response.status_code
                    not in self.RETRYABLE_STATUS_CODES
                ):

                    return {
                        "success": False,
                        "status_code": response.status_code,
                        "url": url,
                        "attempts_count": attempt,
                        "data": data,
                        "error": "http_error",
                    }

                # Error temporal: esperamos y reintentamos.
                if attempt < max_retries:

                    delay = (
                        self.retry_delay
                        * attempt
                    )

                    time.sleep(delay)

                    continue

                return {
                    "success": False,
                    "status_code": response.status_code,
                    "url": url,
                    "attempts_count": attempt,
                    "data": data,
                    "error": "service_unavailable",
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

                    delay = (
                        self.retry_delay
                        * attempt
                    )

                    time.sleep(delay)

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

                    delay = (
                        self.retry_delay
                        * attempt
                    )

                    time.sleep(delay)

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

    # ============================================================
    # WAKE UP / HEALTH
    # ============================================================

    def wake_service(
        self,
    ) -> Dict[str, Any]:

        """
        Despierta PhoneInfoga antes de ejecutar el análisis.

        /api/version es liviano y permite verificar
        que el servidor Go ya está atendiendo.
        """

        return self._request(
            "GET",
            "/api/version",
            retries=self.retries,
        )

    def health(
        self,
    ) -> Dict[str, Any]:

        result = self.wake_service()

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
            "response": result,
        }

    # ============================================================
    # VALIDACIÓN
    # ============================================================

    def validate(
        self,
        phone_number: str,
        default_region: str = "AR",
    ) -> Dict[str, Any]:

        number = self._prepare_number(
            phone_number
        )

        if not number:

            return {
                "success": False,
                "error": "invalid_number",
                "message": (
                    "No se recibió un número válido."
                ),
            }

        endpoint = (
            f"/api/numbers/"
            f"{quote(number, safe='')}"
            f"/validate"
        )

        return self._request(
            "GET",
            endpoint,
        )

    # ============================================================
    # SCANNERS
    # ============================================================

    def _scan(
        self,
        phone_number: str,
        scanner: str,
    ) -> Dict[str, Any]:

        number = self._prepare_number(
            phone_number
        )

        if not number:

            return {
                "success": False,
                "error": "invalid_number",
            }

        endpoint = (
            f"/api/numbers/"
            f"{quote(number, safe='')}"
            f"/scan/"
            f"{scanner}"
        )

        return self._request(
            "GET",
            endpoint,
        )

    def scan_local(
        self,
        phone_number: str,
    ) -> Dict[str, Any]:

        return self._scan(
            phone_number,
            "local",
        )

    def scan_google(
        self,
        phone_number: str,
    ) -> Dict[str, Any]:

        return self._scan(
            phone_number,
            "googlesearch",
        )

    def scan_numverify(
        self,
        phone_number: str,
    ) -> Dict[str, Any]:

        return self._scan(
            phone_number,
            "numverify",
        )

    def scan_ovh(
        self,
        phone_number: str,
    ) -> Dict[str, Any]:

        return self._scan(
            phone_number,
            "ovh",
        )

    # ============================================================
    # GOOGLE RESULT
    # ============================================================

    def _extract_google_result(
        self,
        google_response: Dict[str, Any],
    ) -> Dict[str, Any]:

        if not isinstance(
            google_response,
            dict,
        ):
            return {}

        data = google_response.get(
            "data"
        )

        if not isinstance(
            data,
            dict,
        ):
            return {}

        result = data.get(
            "result"
        )

        if not isinstance(
            result,
            dict,
        ):
            return {}

        return result

    # ============================================================
    # DETECCIÓN DE FUENTE
    # ============================================================

    def _detect_source(
        self,
        url: str,
        dork: str,
    ) -> str:

        text = (
            f"{url} {dork}"
        ).lower()

        known_sources = {
            "facebook.com": "Facebook",
            "instagram.com": "Instagram",
            "twitter.com": "X / Twitter",
            "x.com": "X / Twitter",
            "linkedin.com": "LinkedIn",
            "vk.com": "VK",
            "pastebin.com": "Pastebin",
            "sync.me": "Sync.me",
            "spytox.com": "Spytox",
            "locatefamily.com": "LocateFamily",
            "whycall.me": "WhyCall.me",
            "whocallsyou.de": "WhoCallsYou",
            "numinfo.net": "NumInfo",
            "whosenumber.info": "WhoseNumber",
            "findwhocallsme.com": "FindWhoCallsMe",
            "who-calledme.com": "Who-CalledMe",
            "quinumero.info": "QuiNumero",
            "yellowpages.ca": "YellowPages",
            "phonenumbers.ie": "PhoneNumbers.ie",
        }

        for domain, name in known_sources.items():

            if domain in text:
                return name

        if (
            "ext:pdf" in text
            or "ext:doc" in text
        ):
            return "Documentos públicos"

        return "Google"

    # ============================================================
    # FOOTPRINT
    # ============================================================

    def _build_footprint(
        self,
        category: str,
        item: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:

        if not isinstance(
            item,
            dict,
        ):
            return None

        url = item.get(
            "url"
        )

        dork = item.get(
            "dork"
        )

        number = item.get(
            "number"
        )

        if not url:
            return None

        category_config = (
            self.CATEGORY_MAP.get(
                category,
                {
                    "label": category,
                    "type": category,
                    "priority": 99,
                },
            )
        )

        source = self._detect_source(
            str(url),
            str(dork or ""),
        )

        return {
            "engine": self.ENGINE_ID,
            "source": source,
            "category": (
                category_config["type"]
            ),
            "category_label": (
                category_config["label"]
            ),
            "priority": (
                category_config["priority"]
            ),
            "phone_number": number,
            "query": dork,
            "url": url,

            # PhoneInfoga genera consultas/dorks.
            # No constituyen por sí mismos
            # una coincidencia confirmada.
            "confirmed": False,

            "result_type": "search_query",

            "status": "search_available",
        }

    def _extract_public_footprints(
        self,
        google_response: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        result = self._extract_google_result(
            google_response
        )

        footprints: List[
            Dict[str, Any]
        ] = []

        for category in self.CATEGORY_MAP:

            items = result.get(
                category,
                [],
            )

            if not isinstance(
                items,
                list,
            ):
                continue

            for item in items:

                footprint = self._build_footprint(
                    category,
                    item,
                )

                if footprint:

                    footprints.append(
                        footprint
                    )

        footprints.sort(
            key=lambda item: (
                item.get(
                    "priority",
                    99,
                ),
                item.get(
                    "source",
                    "",
                ),
            )
        )

        return footprints

    # ============================================================
    # AGRUPACIÓN
    # ============================================================

    def _group_footprints(
        self,
        footprints: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:

        groups: Dict[
            str,
            List[Dict[str, Any]],
        ] = {
            "social_media": [],
            "reputation": [],
            "individuals": [],
            "general": [],
            "disposable_providers": [],
        }

        for footprint in footprints:

            category = footprint.get(
                "category"
            )

            if category not in groups:

                groups[category] = []

            groups[category].append(
                footprint
            )

        return groups

    # ============================================================
    # RESUMEN
    # ============================================================

    def _build_summary(
        self,
        scanner_results: Dict[str, Any],
        footprints: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        available: List[str] = []
        failed: List[str] = []

        for scanner, result in (
            scanner_results.items()
        ):

            if result.get(
                "success"
            ):

                available.append(
                    scanner
                )

            else:

                failed.append(
                    scanner
                )

        categories: Dict[str, int] = {}
        sources: Dict[str, int] = {}

        for footprint in footprints:

            category = footprint.get(
                "category",
                "unknown",
            )

            source = footprint.get(
                "source",
                "Unknown",
            )

            categories[category] = (
                categories.get(
                    category,
                    0,
                )
                + 1
            )

            sources[source] = (
                sources.get(
                    source,
                    0,
                )
                + 1
            )

        return {
            "scanners_available": len(
                available
            ),
            "scanners_failed": len(
                failed
            ),
            "footprints_found": len(
                footprints
            ),
            "search_queries_generated": len(
                footprints
            ),
            "confirmed_matches": 0,
            "categories": categories,
            "sources": sources,
        }

    # ============================================================
    # BÚSQUEDA PRINCIPAL
    # ============================================================

    def search(
        self,
        phone_number: str,
        default_region: str = "AR",
    ) -> Dict[str, Any]:

        number = self._prepare_number(
            phone_number
        )

        if not number:

            return {
                "status": "error",
                "phone_number": phone_number,
                "engine": {
                    "id": self.ENGINE_ID,
                    "name": self.ENGINE_NAME,
                    "mode": "live",
                },
                "error": "invalid_phone_number",
                "message": (
                    "El número de teléfono "
                    "está vacío o no es válido."
                ),
                "public_footprints": [],
            }

        # ========================================================
        # 1. WAKE UP PHONEINFOGA
        # ========================================================

        wakeup = self.wake_service()

        # Si PhoneInfoga sigue caído después
        # de los reintentos, evitamos hacer
        # otras cuatro llamadas inútiles.
        if not wakeup.get(
            "success"
        ):

            return {
                "status": "error",

                "phone_number": phone_number,

                "phoneinfoga_number": number,

                "default_region": default_region,

                "engine": {
                    "id": self.ENGINE_ID,
                    "name": self.ENGINE_NAME,
                    "mode": "live",
                },

                "service": {
                    "url": self.base_url,
                },

                "error": "phoneinfoga_unavailable",

                "message": (
                    "PhoneInfoga no respondió "
                    "después de varios intentos."
                ),

                "wakeup": wakeup,

                "validation": {
                    "success": False,
                    "error": (
                        "service_unavailable"
                    ),
                },

                "scanners": {
                    "available": [],
                    "failed": list(
                        self.SCANNERS
                    ),
                },

                "scanner_results": {},

                "public_footprints": [],

                "footprint_groups": (
                    self._group_footprints(
                        []
                    )
                ),

                "summary": {
                    "scanners_available": 0,
                    "scanners_failed": len(
                        self.SCANNERS
                    ),
                    "footprints_found": 0,
                    "search_queries_generated": 0,
                    "confirmed_matches": 0,
                    "categories": {},
                    "sources": {},
                },
            }

        # ========================================================
        # 2. VALIDACIÓN
        # ========================================================

        validation = self.validate(
            phone_number,
            default_region,
        )

        # ========================================================
        # 3. SCANNERS
        # ========================================================

        scanner_results: Dict[
            str,
            Any,
        ] = {}

        scanner_results["local"] = (
            self.scan_local(
                phone_number
            )
        )

        scanner_results["google_search"] = (
            self.scan_google(
                phone_number
            )
        )

        scanner_results["numverify"] = (
            self.scan_numverify(
                phone_number
            )
        )

        scanner_results["ovh"] = (
            self.scan_ovh(
                phone_number
            )
        )

        # ========================================================
        # 4. DISPONIBLES / FALLIDOS
        # ========================================================

        available: List[str] = []
        failed: List[str] = []

        for (
            scanner_name,
            scanner_result,
        ) in scanner_results.items():

            if scanner_result.get(
                "success"
            ):

                available.append(
                    scanner_name
                )

            else:

                failed.append(
                    scanner_name
                )

        # ========================================================
        # 5. FOOTPRINTS
        # ========================================================

        google_result = (
            scanner_results.get(
                "google_search",
                {},
            )
        )

        public_footprints = (
            self._extract_public_footprints(
                google_result
            )
        )

        grouped_footprints = (
            self._group_footprints(
                public_footprints
            )
        )

        # ========================================================
        # 6. SUMMARY
        # ========================================================

        summary = self._build_summary(
            scanner_results,
            public_footprints,
        )

        # ========================================================
        # 7. STATUS
        # ========================================================

        if not available:

            status = "error"

        elif failed:

            status = "partial"

        else:

            status = "completed"

        # ========================================================
        # 8. RESPONSE
        # ========================================================

        return {
            "status": status,

            "phone_number": phone_number,

            "phoneinfoga_number": number,

            "default_region": default_region,

            "engine": {
                "id": self.ENGINE_ID,
                "name": self.ENGINE_NAME,
                "mode": "live",
            },

            "service": {
                "url": self.base_url,
            },

            "wakeup": {
                "success": True,
                "attempts_count": (
                    wakeup.get(
                        "attempts_count",
                        1,
                    )
                ),
            },

            "validation": validation,

            "scanners": {
                "available": available,
                "failed": failed,
            },

            "scanner_results": scanner_results,

            "public_footprints": (
                public_footprints
            ),

            "footprint_groups": (
                grouped_footprints
            ),

            "summary": summary,
        }

    # ============================================================
    # ALIAS
    # ============================================================

    def scan(
        self,
        phone_number: str,
        default_region: str = "AR",
    ) -> Dict[str, Any]:

        return self.search(
            phone_number=phone_number,
            default_region=default_region,
        )


# ================================================================
# INSTANCIA GLOBAL
# ================================================================

phoneinfoga_engine = PhoneInfogaEngine()


# ================================================================
# COMPATIBILIDAD
# ================================================================

def search_phoneinfoga(
    phone_number: str,
    default_region: str = "AR",
) -> Dict[str, Any]:

    return phoneinfoga_engine.search(
        phone_number=phone_number,
        default_region=default_region,
    )


def scan_phoneinfoga(
    phone_number: str,
    default_region: str = "AR",
) -> Dict[str, Any]:

    return phoneinfoga_engine.search(
        phone_number=phone_number,
        default_region=default_region,
    )
