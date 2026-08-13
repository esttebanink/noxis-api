"""Adaptador aislado de OpenSpam para NOXIS.

Usa exclusivamente la API pública documentada por OpenSpam. Este módulo no
está integrado todavía con Phone Intelligence ni modifica sus resúmenes.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional
from urllib.parse import quote

import phonenumbers
import requests


logger = logging.getLogger("noxis.openspam")


class OpenSpamEngine:
    ENGINE_ID = "openspam"
    ENGINE_NAME = "OpenSpam"

    DEFAULT_BASE_URL = "https://api.openspam.es/api"
    DEFAULT_TIMEOUT = 20
    DEFAULT_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1.0

    RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}

    CATEGORY_MAP = {
        "spam": "spam",
        "telemarketing": "telemarketing",
        "telemercadeo": "telemarketing",
        "robocall": "robocall",
        "llamada automatizada": "robocall",
        "fraude": "fraud",
        "fraud": "fraud",
        "estafa": "scam",
        "scam": "scam",
        "cobro de deudas": "debt_collection",
        "debt collection": "debt_collection",
        "debt_collection": "debt_collection",
        "encuesta": "survey",
        "survey": "survey",
        "política": "political",
        "politica": "political",
        "political": "political",
        "otro": "other",
        "otros": "other",
        "other": "other",
        "desconocido": "unknown",
        "unknown": "unknown",
    }

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[int] = None,
        retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.base_url = (
            base_url or os.getenv("OPENSPAM_URL") or self.DEFAULT_BASE_URL
        ).rstrip("/")
        self.api_key = (
            api_key if api_key is not None else os.getenv("OPENSPAM_API_KEY", "")
        ).strip()
        self.timeout = self._positive_int(
            timeout if timeout is not None else os.getenv("OPENSPAM_TIMEOUT"),
            self.DEFAULT_TIMEOUT,
        )
        self.retries = min(
            self._positive_int(
                retries if retries is not None else os.getenv("OPENSPAM_RETRIES"),
                self.DEFAULT_RETRIES,
            ),
            self.DEFAULT_RETRIES,
        )
        self.retry_delay = self._positive_float(
            retry_delay,
            self.DEFAULT_RETRY_DELAY,
        )

        self.session = session or requests.Session()
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
    def _masked_phone(phone_number: str) -> str:
        digits = "".join(char for char in phone_number if char.isdigit())
        if len(digits) <= 4:
            return "****"
        return f"***{digits[-4:]}"

    @staticmethod
    def _normalize_phone(phone_number: str, default_region: str = "AR") -> str:
        raw = str(phone_number or "").strip()
        region = str(default_region or "").strip().upper() or None
        if not raw:
            return ""

        candidates = [raw]
        digits = "".join(char for char in raw if char.isdigit())
        if not raw.startswith("+") and 8 <= len(digits) <= 15:
            # Acepta también un E.164 escrito sin el signo +. El primer intento
            # sigue interpretando correctamente números nacionales por región.
            candidates.append(f"+{digits}")

        for candidate in candidates:
            try:
                parsed = phonenumbers.parse(
                    candidate,
                    None if candidate.startswith("+") else region,
                )
                if not phonenumbers.is_possible_number(parsed):
                    continue
                return phonenumbers.format_number(
                    parsed,
                    phonenumbers.PhoneNumberFormat.E164,
                )
            except phonenumbers.NumberParseException:
                continue
        return ""

    @staticmethod
    def _safe_response_data(response: requests.Response) -> Optional[Dict[str, Any]]:
        try:
            payload = response.json()
        except ValueError:
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _retry_after(response: requests.Response) -> Optional[str]:
        value = response.headers.get("Retry-After")
        return value.strip() if isinstance(value, str) and value.strip() else None

    @classmethod
    def _safe_provider_payload(cls, value: Any) -> Any:
        sensitive_keys = {
            "api_key",
            "apikey",
            "x-api-key",
            "authorization",
            "cookie",
            "cookies",
            "token",
            "access_token",
            "refresh_token",
        }

        if isinstance(value, dict):
            return {
                key: cls._safe_provider_payload(item)
                for key, item in value.items()
                if str(key).strip().lower() not in sensitive_keys
            }

        if isinstance(value, list):
            return [
                cls._safe_provider_payload(item)
                for item in value
            ]

        return value

    def _request(self, method: str, endpoint: str) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        max_attempts = min(max(self.retries, 1), self.DEFAULT_RETRIES)

        for attempt in range(1, max_attempts + 1):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    timeout=self.timeout,
                )
                payload = self._safe_response_data(response)
                retry_after = self._retry_after(response)

                if response.ok:
                    if payload is None:
                        return {
                            "success": False,
                            "status_code": response.status_code,
                            "attempts_count": attempt,
                            "error": "invalid_provider_response",
                        }
                    return {
                        "success": True,
                        "status_code": response.status_code,
                        "attempts_count": attempt,
                        "data": payload,
                    }

                result = {
                    "success": False,
                    "status_code": response.status_code,
                    "attempts_count": attempt,
                    "data": payload or {},
                    "error": "http_error",
                }
                if retry_after:
                    result["retry_after"] = retry_after

                if response.status_code not in self.RETRYABLE_STATUS_CODES:
                    return result

                if attempt < max_attempts:
                    time.sleep(self.retry_delay * attempt)
                    continue

                result["error"] = (
                    "rate_limited"
                    if response.status_code == 429
                    else "service_unavailable"
                )
                return result

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
            except requests.ConnectionError:
                if attempt < max_attempts:
                    time.sleep(self.retry_delay * attempt)
                    continue
                return {
                    "success": False,
                    "status_code": None,
                    "attempts_count": attempt,
                    "error": "service_unavailable",
                }
            except requests.RequestException:
                return {
                    "success": False,
                    "status_code": None,
                    "attempts_count": attempt,
                    "error": "request_error",
                }
            except Exception:
                return {
                    "success": False,
                    "status_code": None,
                    "attempts_count": attempt,
                    "error": "unexpected_error",
                }

        return {"success": False, "error": "unknown_request_error"}

    @staticmethod
    def _optional_non_negative_int(value: Any) -> Optional[int]:
        if value is None or isinstance(value, bool):
            return None
        try:
            return max(int(value), 0)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _normalized_category(cls, value: Any) -> Optional[str]:
        if not isinstance(value, str) or not value.strip():
            return None
        normalized = " ".join(
            value.strip().lower().replace("-", " ").replace("_", " ").split()
        )
        return cls.CATEGORY_MAP.get(normalized, "unknown")

    @staticmethod
    def _provider_not_found(payload: Dict[str, Any]) -> bool:
        if payload.get("success") is not False:
            return False
        searchable = " ".join(
            str(payload.get(key, ""))
            for key in ("error", "message", "mensaje", "detail")
        ).lower()
        return any(
            marker in searchable
            for marker in (
                "no encontrado",
                "no existe",
                "no registrado",
                "sin información",
                "sin informacion",
                "not found",
            )
        )

    def _empty_result(
        self,
        input_phone: str,
        normalized_phone: str,
        status: str,
    ) -> Dict[str, Any]:
        evidence_status = "none" if status == "not_found" else "unavailable"
        return {
            "status": status,
            "engine": {
                "id": self.ENGINE_ID,
                "name": self.ENGINE_NAME,
                "mode": "live",
            },
            "input": input_phone,
            "normalized_phone": normalized_phone,
            "reported": False,
            "reports_count": None,
            "spam_score": None,
            "risk_level": None,
            "category": None,
            "normalized_category": None,
            "last_reported_at": None,
            "possible_spam": False,
            "possible_fraud": False,
            "confirmed_fraud": False,
            "technical": {
                "country": None,
                "region": None,
                "province": None,
                "carrier": None,
                "operator": None,
                "line_type": None,
            },
            "evidence": {
                "reputation": {
                    "status": evidence_status,
                    "reported": False,
                    "reports_count": None,
                    "source": self.ENGINE_NAME,
                    "possible_spam": False,
                    "possible_fraud": False,
                    "confirmed_fraud": False,
                    "description": (
                        "Los reportes de reputación no confirman por sí solos "
                        "fraude, identidad ni autoría de llamadas."
                    ),
                }
            },
            "raw": {},
        }

    def _normalize_response(
        self,
        input_phone: str,
        normalized_phone: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        if self._provider_not_found(payload):
            result = self._empty_result(input_phone, normalized_phone, "not_found")
            result["reports_count"] = 0
            result["evidence"]["reputation"]["reports_count"] = 0
            result["raw"] = payload
            return result

        if payload.get("success") is not True or not isinstance(payload.get("data"), dict):
            result = self._empty_result(input_phone, normalized_phone, "error")
            result["error"] = "invalid_provider_response"
            result["raw"] = payload
            return result

        data = payload["data"]
        reports_count = self._optional_non_negative_int(data.get("reportes"))
        category = data.get("tipo") if isinstance(data.get("tipo"), str) else None
        normalized_category = self._normalized_category(category)
        reported = reports_count is not None and reports_count > 0
        possible_fraud = reported and normalized_category in {"fraud", "scam"}
        possible_spam = reported or normalized_category in {
            "spam",
            "telemarketing",
            "robocall",
            "fraud",
            "scam",
        }

        result = self._empty_result(input_phone, normalized_phone, "completed")
        result.update(
            {
                "normalized_phone": data.get("telefono") or normalized_phone,
                "reported": reported,
                "reports_count": reports_count,
                "spam_score": data.get("spam_score"),
                "risk_level": data.get("nivel_peligro"),
                "category": category,
                "normalized_category": normalized_category,
                "last_reported_at": (
                    data.get("fecha_ultimo_reporte")
                    or data.get("last_reported_at")
                    or data.get("fecha_deteccion")
                ),
                "possible_spam": possible_spam,
                "possible_fraud": possible_fraud,
                "confirmed_fraud": False,
                "technical": {
                    "country": data.get("pais") or data.get("country"),
                    "region": data.get("region"),
                    "province": data.get("provincia"),
                    "carrier": data.get("carrier"),
                    "operator": data.get("operadora") or data.get("operator"),
                    "line_type": data.get("line_type") or data.get("tipo_linea"),
                },
                "evidence": {
                    "reputation": {
                        "status": "available",
                        "reported": reported,
                        "reports_count": reports_count,
                        "source": self.ENGINE_NAME,
                        "possible_spam": possible_spam,
                        "possible_fraud": possible_fraud,
                        "confirmed_fraud": False,
                        "description": (
                            "Los reportes de reputación no confirman por sí solos "
                            "fraude, identidad ni autoría de llamadas."
                        ),
                    }
                },
                "raw": payload,
            }
        )
        return result

    def search(
        self,
        phone_number: str,
        default_region: str = "AR",
    ) -> Dict[str, Any]:
        input_phone = str(phone_number or "").strip()
        normalized_phone = self._normalize_phone(input_phone, default_region)
        logger.info(
            "openspam_search_started phone=%s",
            self._masked_phone(normalized_phone or input_phone),
        )

        if not normalized_phone:
            result = self._empty_result(input_phone, normalized_phone, "error")
            result["error"] = "invalid_number"
            result["message"] = "El número no pudo normalizarse a formato E.164."
            logger.warning("openspam_error error=invalid_number")
            return result

        if not self.api_key:
            result = self._empty_result(
                input_phone,
                normalized_phone,
                "configuration_required",
            )
            result["error"] = "missing_api_key"
            result["message"] = "OPENSPAM_API_KEY no está configurada."
            logger.warning("openspam_configuration_required")
            return result

        endpoint_phone = quote(normalized_phone, safe="+")
        response = self._request("GET", f"/number/{endpoint_phone}")

        if response.get("success"):
            result = self._normalize_response(
                input_phone,
                normalized_phone,
                response.get("data", {}),
            )
            if result["status"] == "not_found":
                logger.info("openspam_not_found")
            elif result["status"] == "completed":
                logger.info("openspam_search_completed")
            else:
                logger.warning("openspam_error error=%s", result.get("error"))
            return result

        status_code = response.get("status_code")
        error = response.get("error")
        provider_diagnostics = None

        if status_code in {401, 403}:
            status = "configuration_required"
            normalized_error = "authentication_failed"

            provider_payload = response.get("data")
            safe_provider_payload = self._safe_provider_payload(
                provider_payload
                if isinstance(provider_payload, dict)
                else {}
            )

            provider_diagnostics = {
                "status_code": status_code,
                "response": safe_provider_payload,
                "api_key_configured": bool(self.api_key),
                "api_key_prefix_valid": self.api_key.startswith("sk-"),
            }

            logger.warning("openspam_configuration_required")
        elif status_code == 429 or error == "rate_limited":
            status = "rate_limited"
            normalized_error = "rate_limited"
            logger.warning("openspam_rate_limited")
        elif error == "timeout":
            status = "timeout"
            normalized_error = "timeout"
            logger.warning("openspam_error error=timeout")
        elif status_code in {408, 425, 500, 502, 503, 504} or error == "service_unavailable":
            status = "unavailable"
            normalized_error = "service_unavailable"
            logger.warning("openspam_error error=service_unavailable")
        elif status_code == 404:
            # La documentación oficial define 404 como endpoint incorrecto,
            # no como ausencia de información para un número.
            status = "error"
            normalized_error = "endpoint_not_found"
            logger.warning("openspam_error error=endpoint_not_found")
        else:
            status = "error"
            normalized_error = error or "provider_error"
            logger.warning("openspam_error error=%s", normalized_error)

        result = self._empty_result(input_phone, normalized_phone, status)
        result["error"] = normalized_error
        if response.get("retry_after") is not None:
            result["retry_after"] = response["retry_after"]
        if provider_diagnostics is not None:
            result["provider_diagnostics"] = provider_diagnostics
            result["raw"] = provider_diagnostics["response"]
        elif isinstance(response.get("data"), dict):
            result["raw"] = response["data"]
        return result

    def lookup(
        self,
        phone_number: str,
        default_region: str = "AR",
    ) -> Dict[str, Any]:
        return self.search(phone_number, default_region=default_region)

    def health(self) -> Dict[str, Any]:
        # OpenSpam no documenta un endpoint health público. Evitamos consumir
        # cuota y nos limitamos a verificar la configuración local.
        configured = bool(self.api_key)
        return {
            "status": "configured" if configured else "configuration_required",
            "engine": {
                "id": self.ENGINE_ID,
                "name": self.ENGINE_NAME,
                "mode": "live",
            },
            "base_url": self.base_url,
            "error": None if configured else "missing_api_key",
        }


openspam_engine = OpenSpamEngine()


def search_openspam(
    phone_number: str,
    default_region: str = "AR",
) -> Dict[str, Any]:
    return openspam_engine.search(phone_number, default_region=default_region)


def lookup_openspam(
    phone_number: str,
    default_region: str = "AR",
) -> Dict[str, Any]:
    return openspam_engine.lookup(phone_number, default_region=default_region)
