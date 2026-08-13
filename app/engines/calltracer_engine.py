"""NOXIS CallTracer engine.

Consulta la API pública documentada por CallTracer y normaliza señales
comunitarias de reputación telefónica sin confirmar fraude ni identidad.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional
from urllib.parse import quote

import phonenumbers
import requests


logger = logging.getLogger("noxis.calltracer")


class CallTracerEngine:
    ENGINE_ID = "calltracer"
    ENGINE_NAME = "CallTracer"

    DEFAULT_BASE_URL = "https://calltracer.io"
    DEFAULT_TIMEOUT = 20
    DEFAULT_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1.0

    RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}

    CATEGORY_MAP = {
        "spam": "spam",
        "telemarketing": "telemarketing",
        "telemarketer": "telemarketing",
        "robocall": "robocall",
        "robot call": "robocall",
        "fraud": "fraud",
        "scam": "scam",
        "debt collection": "debt_collection",
        "debt collector": "debt_collection",
        "debt_collection": "debt_collection",
    }

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
    ) -> None:
        self.base_url = (
            base_url
            or os.getenv("CALLTRACER_URL")
            or self.DEFAULT_BASE_URL
        ).rstrip("/")

        self.timeout = self._positive_int(
            timeout or os.getenv("CALLTRACER_TIMEOUT"),
            self.DEFAULT_TIMEOUT,
        )
        self.retries = min(
            self._positive_int(
                retries or os.getenv("CALLTRACER_RETRIES"),
                self.DEFAULT_RETRIES,
            ),
            self.DEFAULT_RETRIES,
        )
        self.retry_delay = self._positive_float(
            retry_delay or os.getenv("CALLTRACER_RETRY_DELAY"),
            self.DEFAULT_RETRY_DELAY,
        )

        # Reservado para compatibilidad futura. La API pública actual no exige
        # autenticación. Solo se envía si el operador configura la variable.
        self.api_key = (os.getenv("CALLTRACER_API_KEY") or "").strip()

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "NOXIS PhoneReputation",
            }
        )
        if self.api_key:
            self.session.headers["X-API-Key"] = self.api_key

    @staticmethod
    def _positive_int(value: Any, fallback: int) -> int:
        try:
            parsed = int(value)
            return parsed if parsed > 0 else fallback
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _positive_float(value: Any, fallback: float) -> float:
        try:
            parsed = float(value)
            return parsed if parsed >= 0 else fallback
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _safe_response_data(response: requests.Response) -> Dict[str, Any]:
        try:
            data = response.json()
            return data if isinstance(data, dict) else {"value": data}
        except ValueError:
            text = response.text or ""
            return {"raw": text[:2000]}

    def _request(
        self,
        method: str,
        endpoint: str,
        retries: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        max_attempts = min(max(int(retries or self.retries), 1), 3)

        for attempt in range(1, max_attempts + 1):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    timeout=self.timeout,
                    **kwargs,
                )
                data = self._safe_response_data(response)

                if response.ok:
                    return {
                        "success": True,
                        "status_code": response.status_code,
                        "attempts_count": attempt,
                        "data": data,
                    }

                if response.status_code not in self.RETRYABLE_STATUS_CODES:
                    return {
                        "success": False,
                        "status_code": response.status_code,
                        "attempts_count": attempt,
                        "data": data,
                        "error": "http_error",
                    }

                if attempt < max_attempts:
                    time.sleep(self.retry_delay * attempt)
                    continue

                error = (
                    "rate_limited"
                    if response.status_code == 429
                    else "service_unavailable"
                )
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "attempts_count": attempt,
                    "data": data,
                    "error": error,
                }

            except requests.Timeout:
                if attempt < max_attempts:
                    time.sleep(self.retry_delay * attempt)
                    continue
                return {
                    "success": False,
                    "status_code": None,
                    "attempts_count": attempt,
                    "error": "timeout",
                }
            except requests.RequestException as exc:
                if attempt < max_attempts:
                    time.sleep(self.retry_delay * attempt)
                    continue
                return {
                    "success": False,
                    "status_code": None,
                    "attempts_count": attempt,
                    "error": "request_error",
                    "detail": str(exc),
                }
            except Exception as exc:
                return {
                    "success": False,
                    "status_code": None,
                    "attempts_count": attempt,
                    "error": "unexpected_error",
                    "detail": str(exc),
                }

        return {"success": False, "error": "unknown_request_error"}

    @staticmethod
    def _normalize_phone(
        phone_number: str,
        default_region: Optional[str] = None,
    ) -> str:
        raw = str(phone_number or "").strip()
        if not raw:
            return ""

        try:
            parsed = phonenumbers.parse(raw, default_region)
            if phonenumbers.is_possible_number(parsed):
                return phonenumbers.format_number(
                    parsed,
                    phonenumbers.PhoneNumberFormat.E164,
                )
        except phonenumbers.NumberParseException:
            pass

        digits = "".join(character for character in raw if character.isdigit())
        if raw.startswith("+") and digits:
            return f"+{digits}"
        return digits

    @classmethod
    def _normalized_category(cls, value: Any) -> Optional[str]:
        if not isinstance(value, str) or not value.strip():
            return None
        normalized = value.strip().lower().replace("-", " ")
        return cls.CATEGORY_MAP.get(normalized, "unknown")

    def _empty_result(self, phone_number: str, status: str) -> Dict[str, Any]:
        return {
            "status": status,
            "engine": {
                "id": self.ENGINE_ID,
                "name": self.ENGINE_NAME,
                "mode": "live",
            },
            "phone_number": phone_number,
            "reported": False,
            "spam_score": None,
            "reports_count": 0,
            "last_reported_at": None,
            "category": None,
            "normalized_category": None,
            "possible_spam": False,
            "possible_fraud": False,
            "technical": {
                "country": None,
                "carrier": None,
                "line_type": None,
                "location": None,
            },
            "evidence": {
                "reputation": {
                    "status": "unavailable" if status not in {"not_found"} else "none",
                    "reported": False,
                    "reports_count": 0,
                    "source": self.ENGINE_NAME,
                    "confirmed_fraud": False,
                }
            },
            "raw": {},
        }

    def _normalize_response(
        self,
        phone_number: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not data:
            return self._empty_result(phone_number, "not_found")

        reports = data.get("reports")
        reports = reports if isinstance(reports, dict) else {}

        reports_count = self._non_negative_int(
            reports.get("total", data.get("reports_count"))
        )
        spam_score = reports.get("spam_score", data.get("spam_score"))
        category = reports.get("category", data.get("category"))
        last_reported_at = reports.get(
            "last_reported_at", data.get("last_reported_at")
        )

        explicitly_reported = data.get("reported") is True or data.get("is_reported") is True
        reported = explicitly_reported or reports_count > 0

        result = self._empty_result(phone_number, "completed")
        result.update(
            {
                "phone_number": data.get("number") or phone_number,
                "reported": reported,
                "spam_score": spam_score,
                "reports_count": reports_count,
                "last_reported_at": last_reported_at,
                "category": category,
                "normalized_category": self._normalized_category(category),
                "possible_spam": reported,
                "possible_fraud": False,
                "technical": {
                    "country": data.get("country") or data.get("country_iso"),
                    "carrier": data.get("carrier"),
                    "line_type": data.get("number_type") or data.get("line_type"),
                    "location": data.get("location"),
                },
                "evidence": {
                    "reputation": {
                        "status": "available",
                        "reported": reported,
                        "reports_count": reports_count,
                        "source": self.ENGINE_NAME,
                        "confirmed_fraud": False,
                    }
                },
                "raw": data,
            }
        )
        return result

    @staticmethod
    def _non_negative_int(value: Any) -> int:
        try:
            return max(int(value), 0)
        except (TypeError, ValueError):
            return 0

    def search(
        self,
        phone_number: str,
        default_region: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_phone = self._normalize_phone(phone_number, default_region)
        logger.info("calltracer_search_started")

        if not normalized_phone:
            result = self._empty_result(normalized_phone, "error")
            result["input"] = str(phone_number or "")
            result["normalized_phone"] = normalized_phone
            result["error"] = "invalid_number"
            logger.warning("calltracer_error")
            return result

        endpoint_number = normalized_phone.lstrip("+")
        response = self._request(
            "GET",
            f"/api/lookup/{quote(endpoint_number, safe='')}",
        )

        if response.get("success"):
            result = self._normalize_response(
                normalized_phone,
                response.get("data", {}),
            )
            result["input"] = str(phone_number or "")
            result["normalized_phone"] = normalized_phone
            logger.info("calltracer_search_completed")
            return result

        status_code = response.get("status_code")
        error = response.get("error")

        if status_code == 429 or error == "rate_limited":
            status = "rate_limited"
            logger.warning("calltracer_rate_limited")
        elif error == "timeout":
            status = "timeout"
            logger.warning("calltracer_error")
        elif status_code in {404, 422}:
            status = "not_found"
            logger.info("calltracer_search_completed")
        elif status_code in {500, 502, 503, 504} or error == "service_unavailable":
            status = "unavailable"
            logger.warning("calltracer_error")
        else:
            status = "error"
            logger.warning("calltracer_error")

        result = self._empty_result(normalized_phone, status)
        result["input"] = str(phone_number or "")
        result["normalized_phone"] = normalized_phone
        result["error"] = error
        return result

    def lookup(
        self,
        phone_number: str,
        default_region: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.search(phone_number, default_region=default_region)

    def health(self) -> Dict[str, Any]:
        response = self._request("GET", "/", retries=1)
        return {
            "status": "available" if response.get("success") else "unavailable",
            "engine": {
                "id": self.ENGINE_ID,
                "name": self.ENGINE_NAME,
                "mode": "live",
            },
            "base_url": self.base_url,
        }


calltracer_engine = CallTracerEngine()


def search_calltracer(
    phone_number: str,
    default_region: Optional[str] = None,
) -> Dict[str, Any]:
    return calltracer_engine.search(phone_number, default_region=default_region)


def lookup_calltracer(
    phone_number: str,
    default_region: Optional[str] = None,
) -> Dict[str, Any]:
    return calltracer_engine.lookup(phone_number, default_region=default_region)


if __name__ == "__main__":
    import json
    import sys

    value = sys.argv[1] if len(sys.argv) > 1 else "+542932520063"
    print(json.dumps(search_calltracer(value), ensure_ascii=False, indent=2))
