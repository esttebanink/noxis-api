"""
NOXIS - PhoneInfoga Engine
==========================

Motor de integración entre NOXIS API y el servicio PhoneInfoga
desplegado en Render.

Servicio PhoneInfoga:
https://noxis-phoneinfoga.onrender.com

Funciones:
- Validar números mediante PhoneInfoga
- Ejecutar scanners disponibles
- Procesar resultados de Google Search
- Convertir dorks de PhoneInfoga en footprints utilizables por NOXIS
- Mantener tolerancia a errores parciales
- No interrumpir NOXIS si un scanner falla
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests


class PhoneInfogaEngine:
    """
    Cliente de PhoneInfoga para NOXIS.

    El motor está diseñado para aceptar fallos parciales:
    si un scanner falla, los demás resultados siguen siendo devueltos.
    """

    ENGINE_ID = "phoneinfoga"
    ENGINE_NAME = "PhoneInfoga"

    DEFAULT_BASE_URL = "https://noxis-phoneinfoga.onrender.com"

    DEFAULT_TIMEOUT = 25

    # Scanners que actualmente queremos consultar.
    SCANNERS = (
        "local",
        "googlesearch",
        "numverify",
        "ovh",
    )

    # Traducción interna de categorías de PhoneInfoga a NOXIS.
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

        self.session = requests.Session()

        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "NOXIS/0.1 PhoneIntelligence",
            }
        )

    # ============================================================
    # UTILIDADES
    # ============================================================

    def _prepare_number(self, phone_number: str) -> str:
        """
        Prepara el número para las rutas de PhoneInfoga.

        Ejemplo:
            +542932520063
        pasa a:
            542932520063
        """

        if phone_number is None:
            return ""

        raw = str(phone_number).strip()

        cleaned = "".join(
            character
            for character in raw
            if character.isdigit()
        )

        return cleaned

    def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Ejecuta una petición HTTP segura contra PhoneInfoga.
        Nunca lanza una excepción hacia NOXIS.
        """

        url = f"{self.base_url}{endpoint}"

        try:

            response = self.session.request(
                method=method,
                url=url,
                timeout=self.timeout,
                **kwargs,
            )

            try:
                data = response.json()
            except ValueError:
                data = {
                    "raw": response.text
                }

            return {
                "success": response.ok,
                "status_code": response.status_code,
                "url": url,
                "data": data,
            }

        except requests.Timeout as exc:

            return {
                "success": False,
                "status_code": None,
                "url": url,
                "error": "timeout",
                "detail": str(exc),
            }

        except requests.RequestException as exc:

            return {
                "success": False,
                "status_code": None,
                "url": url,
                "error": "request_error",
                "detail": str(exc),
            }

        except Exception as exc:

            return {
                "success": False,
                "status_code": None,
                "url": url,
                "error": "unexpected_error",
                "detail": str(exc),
            }

    # ============================================================
    # HEALTH
    # ============================================================

    def health(self) -> Dict[str, Any]:
        """
        Comprueba si PhoneInfoga responde.
        """

        result = self._request(
            "GET",
            "/api/version",
        )

        return {
            "engine": {
                "id": self.ENGINE_ID,
                "name": self.ENGINE_NAME,
                "mode": "live",
            },
            "service": {
                "url": self.base_url,
            },
            "available": result.get("success", False),
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

        number = self._prepare_number(phone_number)

        if not number:

            return {
                "success": False,
                "error": "invalid_number",
                "message": "No se recibió un número válido.",
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

        number = self._prepare_number(phone_number)

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
    # EXTRACCIÓN DE GOOGLE SEARCH
    # ============================================================

    def _extract_google_result(
        self,
        google_response: Dict[str, Any],
    ) -> Dict[str, Any]:

        """
        Obtiene el objeto result real devuelto por PhoneInfoga.

        Estructura observada:

        data
          success
          result
            social_media
            disposable_providers
            reputation
            individuals
            general
        """

        if not isinstance(google_response, dict):
            return {}

        data = google_response.get("data")

        if not isinstance(data, dict):
            return {}

        result = data.get("result")

        if not isinstance(result, dict):
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

        text = f"{url} {dork}".lower()

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

        if "ext:pdf" in text or "ext:doc" in text:
            return "Documentos públicos"

        return "Google"

    # ============================================================
    # FOOTPRINTS
    # ============================================================

    def _build_footprint(
        self,
        category: str,
        item: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:

        if not isinstance(item, dict):
            return None

        url = item.get("url")
        dork = item.get("dork")
        number = item.get("number")

        if not url:
            return None

        category_config = self.CATEGORY_MAP.get(
            category,
            {
                "label": category,
                "type": category,
                "priority": 99,
            },
        )

        source = self._detect_source(
            str(url),
            str(dork or ""),
        )

        return {
            "engine": self.ENGINE_ID,
            "source": source,
            "category": category_config["type"],
            "category_label": category_config["label"],
            "priority": category_config["priority"],
            "phone_number": number,
            "query": dork,
            "url": url,

            # MUY IMPORTANTE:
            # PhoneInfoga está generando una consulta de búsqueda.
            # Esto NO significa que haya confirmado que el número
            # existe en esa plataforma.
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

        footprints: List[Dict[str, Any]] = []

        for category in self.CATEGORY_MAP:

            items = result.get(category, [])

            if not isinstance(items, list):
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
                item.get("priority", 99),
                item.get("source", ""),
            )
        )

        return footprints

    # ============================================================
    # AGRUPACIÓN PARA FRONTEND
    # ============================================================

    def _group_footprints(
        self,
        footprints: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:

        groups: Dict[str, List[Dict[str, Any]]] = {
            "social_media": [],
            "reputation": [],
            "individuals": [],
            "general": [],
            "disposable_providers": [],
        }

        for footprint in footprints:

            category = footprint.get("category")

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

        for scanner, result in scanner_results.items():

            if result.get("success"):
                available.append(scanner)
            else:
                failed.append(scanner)

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
                categories.get(category, 0) + 1
            )

            sources[source] = (
                sources.get(source, 0) + 1
            )

        return {
            "scanners_available": len(available),
            "scanners_failed": len(failed),
            "footprints_found": len(footprints),
            "search_queries_generated": len(footprints),
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

        """
        Método principal utilizado por NOXIS.

        IMPORTANTE:
        Este método debe conservarse con el nombre `search`
        porque phone_engine.py lo utiliza directamente.
        """

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
                "message": "El número de teléfono está vacío o no es válido.",
                "public_footprints": [],
            }

        # --------------------------------------------------------
        # VALIDACIÓN
        # --------------------------------------------------------

        validation = self.validate(
            phone_number,
            default_region,
        )

        # --------------------------------------------------------
        # SCANNERS
        # --------------------------------------------------------

        scanner_results: Dict[str, Any] = {}

        scanner_results["local"] = self.scan_local(
            phone_number
        )

        scanner_results["google_search"] = self.scan_google(
            phone_number
        )

        scanner_results["numverify"] = self.scan_numverify(
            phone_number
        )

        scanner_results["ovh"] = self.scan_ovh(
            phone_number
        )

        # --------------------------------------------------------
        # SCANNERS DISPONIBLES / FALLIDOS
        # --------------------------------------------------------

        available: List[str] = []

        failed: List[str] = []

        for scanner_name, scanner_result in scanner_results.items():

            if scanner_result.get("success"):
                available.append(
                    scanner_name
                )
            else:
                failed.append(
                    scanner_name
                )

        # --------------------------------------------------------
        # EXTRAER FOOTPRINTS
        # --------------------------------------------------------

        google_result = scanner_results.get(
            "google_search",
            {},
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

        # --------------------------------------------------------
        # RESUMEN
        # --------------------------------------------------------

        summary = self._build_summary(
            scanner_results,
            public_footprints,
        )

        # --------------------------------------------------------
        # ESTADO GENERAL
        # --------------------------------------------------------

        if not available:

            status = "error"

        elif failed:

            status = "partial"

        else:

            status = "completed"

        # --------------------------------------------------------
        # RESPUESTA FINAL
        # --------------------------------------------------------

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

            "validation": validation,

            "scanners": {
                "available": available,
                "failed": failed,
            },

            "scanner_results": scanner_results,

            "public_footprints": public_footprints,

            "footprint_groups": grouped_footprints,

            "summary": summary,
        }

    # ============================================================
    # ALIAS DE COMPATIBILIDAD
    # ============================================================

    def scan(
        self,
        phone_number: str,
        default_region: str = "AR",
    ) -> Dict[str, Any]:

        """
        Alias para mantener compatibilidad con código anterior.
        """

        return self.search(
            phone_number=phone_number,
            default_region=default_region,
        )


# ================================================================
# INSTANCIA GLOBAL OPCIONAL
# ================================================================

phoneinfoga_engine = PhoneInfogaEngine()


# ================================================================
# FUNCIONES DE COMPATIBILIDAD
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
