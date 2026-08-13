"""
NOXIS API
=========

Backend principal de NOXIS Intelligence Platform.

Motores:
- Maigret: Username Intelligence
- Google libphonenumber: Phone Intelligence
- PhoneInfoga: Phone OSINT
- Holehe: Email Intelligence

Principio:
Una coincidencia técnica o una consulta OSINT disponible
NO implica identidad confirmada.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ============================================================
# NOXIS ENGINES
# ============================================================

from app.engines.maigret_engine import search_username
from app.engines.phone_engine import analyze_phone
from app.engines.holehe_engine import search_holehe
from app.engines.calltracer_engine import search_calltracer


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="NOXIS API",
    description="API principal de NOXIS Intelligence Platform",
    version="0.4.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# REQUEST MODELS
# ============================================================

class UsernameSearchRequest(BaseModel):
    username: str = Field(
        ...,
        min_length=1,
        description="Username o alias a investigar",
    )

    limit: int = Field(
        default=20,
        ge=1,
        le=500,
        description="Cantidad máxima de sitios a consultar",
    )


class PhoneSearchRequest(BaseModel):
    phone_number: str = Field(
        ...,
        min_length=1,
        description="Número de teléfono",
    )

    default_region: str = Field(
        default="AR",
        min_length=2,
        max_length=2,
        description="Código ISO de región",
    )


class EmailSearchRequest(BaseModel):
    email: str = Field(
        ...,
        min_length=3,
        description="Correo electrónico a investigar",
    )


class CallTracerTestRequest(BaseModel):
    phone_number: str = Field(
        ...,
        min_length=1,
        description="Número para prueba aislada de CallTracer",
    )

    default_region: str = Field(
        default="AR",
        min_length=2,
        max_length=2,
    )


# ============================================================
# HELPERS PHONE OSINT
# ============================================================

def normalize_phoneinfoga_status(
    phoneinfoga: Dict[str, Any],
) -> str:

    if not isinstance(phoneinfoga, dict):
        return "error"

    status = phoneinfoga.get("status")

    if status in {
        "completed",
        "partial",
        "error",
    }:
        return status

    return "unknown"


def extract_public_footprints(
    phoneinfoga: Dict[str, Any],
) -> list:

    if not isinstance(phoneinfoga, dict):
        return []

    footprints = phoneinfoga.get(
        "public_footprints",
        [],
    )

    if not isinstance(footprints, list):
        return []

    return footprints


def extract_footprint_groups(
    phoneinfoga: Dict[str, Any],
) -> Dict[str, Any]:

    default_groups = {
        "social_media": [],
        "reputation": [],
        "individuals": [],
        "general": [],
        "disposable_providers": [],
    }

    if not isinstance(phoneinfoga, dict):
        return default_groups

    groups = phoneinfoga.get(
        "footprint_groups",
        {},
    )

    if not isinstance(groups, dict):
        return default_groups

    normalized = dict(default_groups)

    for key, value in groups.items():
        if isinstance(value, list):
            normalized[key] = value

    return normalized


def extract_osint_summary(
    phoneinfoga: Dict[str, Any],
) -> Dict[str, Any]:

    default_summary = {
        "scanners_available": 0,
        "scanners_skipped": 0,
        "scanners_failed": 0,
        "footprints_found": 0,
        "search_queries_generated": 0,
        "confirmed_matches": 0,
        "categories": {},
        "sources": {},
    }

    if not isinstance(phoneinfoga, dict):
        return default_summary

    summary = phoneinfoga.get(
        "summary",
        {},
    )

    if not isinstance(summary, dict):
        return default_summary

    normalized = dict(default_summary)
    normalized.update(summary)

    # Una consulta OSINT no representa
    # una identidad o coincidencia confirmada.
    normalized["confirmed_matches"] = 0

    return normalized


def build_reputation(
    footprint_groups: Dict[str, Any],
) -> Dict[str, Any]:

    reputation_items = footprint_groups.get(
        "reputation",
        [],
    )

    if not isinstance(reputation_items, list):
        reputation_items = []

    return {
        "status": (
            "search_available"
            if reputation_items
            else "not_checked"
        ),
        "confirmed": False,
        "queries_available": len(
            reputation_items
        ),
        "matches_confirmed": 0,
        "items": reputation_items,
    }


# ============================================================
# ROOT
# ============================================================

@app.get("/")
async def root() -> Dict[str, Any]:

    return {
        "status": "ok",
        "platform": "NOXIS",
        "api_version": "0.4.0",
        "mode": "live",

        "modules": {
            "username_intelligence": True,
            "phone_intelligence": True,
            "email_intelligence": True,
        },

        "engines": {
            "maigret": {
                "enabled": True,
                "mode": "live",
            },

            "phonenumbers": {
                "enabled": True,
                "mode": "live",
            },

            "phoneinfoga": {
                "enabled": True,
                "mode": "live",
            },

            "holehe": {
                "enabled": True,
                "mode": "live",
            },
        },
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
async def health() -> Dict[str, Any]:

    return {
        "status": "ok",
        "platform": "NOXIS",
        "api_version": "0.4.0",
    }


# ============================================================
# API INFO
# ============================================================

@app.get("/api/v1/info")
async def api_info() -> Dict[str, Any]:

    return {
        "platform": "NOXIS",
        "api_version": "0.4.0",
        "mode": "live",

        "modules": {
            "username_intelligence": {
                "enabled": True,
                "engine": "Maigret",
            },

            "phone_intelligence": {
                "enabled": True,
                "engines": [
                    "Google libphonenumber",
                    "PhoneInfoga",
                ],
            },

            "email_intelligence": {
                "enabled": True,
                "engines": [
                    "Holehe",
                ],
            },
        },

        "principles": {
            "technical_match_is_identity": False,
            "search_query_is_confirmation": False,
            "confirmed_identity_required": True,
        },
    }


# ============================================================
# USERNAME INTELLIGENCE
# ============================================================

@app.post("/api/v1/search/username")
async def username_search(
    request: UsernameSearchRequest,
) -> Dict[str, Any]:

    username = (
        request.username
        .strip()
        .lstrip("@")
    )

    if not username:
        raise HTTPException(
            status_code=400,
            detail="Username requerido",
        )

    try:

        result = await search_username(
            username=username,
            limit=request.limit,
        )

        return result

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except FileNotFoundError as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Error ejecutando Username Intelligence: "
                f"{exc}"
            ),
        ) from exc


# ============================================================
# PHONE INTELLIGENCE
# ============================================================

@app.post("/api/v1/search/phone")
async def phone_search(
    request: PhoneSearchRequest,
) -> Dict[str, Any]:

    phone_number = request.phone_number.strip()

    default_region = (
        request.default_region
        or "AR"
    ).strip().upper()

    if not phone_number:
        raise HTTPException(
            status_code=400,
            detail="Número de teléfono requerido",
        )

    try:

        result = await analyze_phone(
            phone_number=phone_number,
            default_region=default_region,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Error ejecutando Phone Intelligence: "
                f"{exc}"
            ),
        ) from exc

    if not isinstance(result, dict):
        raise HTTPException(
            status_code=500,
            detail=(
                "Phone Intelligence devolvió "
                "un formato inesperado"
            ),
        )

    # ========================================================
    # PHONEINFOGA
    # ========================================================

    phoneinfoga = result.get(
        "phoneinfoga",
        {},
    )

    if not isinstance(
        phoneinfoga,
        dict,
    ):
        phoneinfoga = {}

    phoneinfoga_status = (
        normalize_phoneinfoga_status(
            phoneinfoga
        )
    )

    # ========================================================
    # CALLTRACER
    # ========================================================

    calltracer = result.get(
        "calltracer",
        {},
    )

    if not isinstance(
        calltracer,
        dict,
    ):
        calltracer = {}

    calltracer_status = calltracer.get(
        "status",
        "unknown",
    )

    valid_calltracer_statuses = {
        "completed",
        "not_found",
        "rate_limited",
        "timeout",
        "unavailable",
        "error",
    }

    if calltracer_status not in valid_calltracer_statuses:
        calltracer_status = "error"

    calltracer_available = (
        calltracer_status
        in {
            "completed",
            "not_found",
        }
    )

    calltracer_reported = (
        calltracer.get("reported") is True
    )

    calltracer_spam_score = (
        calltracer.get("spam_score")
    )

    if not calltracer_available:
        reputation_risk = "unknown"

    elif not calltracer_reported:
        reputation_risk = "low"

    elif calltracer_spam_score is None:
        reputation_risk = "medium"

    else:
        try:
            numeric_spam_score = float(
                calltracer_spam_score
            )

            if numeric_spam_score < 40:
                reputation_risk = "low"
            elif numeric_spam_score < 70:
                reputation_risk = "medium"
            else:
                reputation_risk = "high"

        except (TypeError, ValueError):
            reputation_risk = "medium"

    reputation_sources = {
        "calltracer": {
            "status": calltracer_status,
            "reported": calltracer_reported,
            "spam_score": calltracer_spam_score,
            "reports_count": calltracer.get(
                "reports_count",
                0,
            ),
            "last_reported_at": calltracer.get(
                "last_reported_at"
            ),
            "category": calltracer.get(
                "category"
            ),
            "normalized_category": calltracer.get(
                "normalized_category"
            ),
            "confirmed_fraud": False,
        }
    }

    reputation_summary = {
        "sources_checked": 1,
        "sources_available": (
            1
            if calltracer_available
            else 0
        ),
        "sources_reporting": (
            1
            if calltracer_reported
            else 0
        ),
        "reported": calltracer_reported,
        "spam_score": calltracer_spam_score,
        "risk": reputation_risk,
    }

    # ========================================================
    # FOOTPRINTS
    # ========================================================

    public_footprints = (
        extract_public_footprints(
            phoneinfoga
        )
    )

    footprint_groups = (
        extract_footprint_groups(
            phoneinfoga
        )
    )

    osint_summary = (
        extract_osint_summary(
            phoneinfoga
        )
    )

    reputation = build_reputation(
        footprint_groups
    )

    # ========================================================
    # ENGINES
    # ========================================================

    existing_engines = result.get(
        "engines",
        {},
    )

    if not isinstance(
        existing_engines,
        dict,
    ):
        existing_engines = {}

    technical_engine = (
        existing_engines.get(
            "technical",
            {
                "id": "phonenumbers",
                "name": (
                    "Google libphonenumber"
                ),
                "mode": "live",
                "status": "completed",
            },
        )
    )

    osint_engine = {
        "id": "phoneinfoga",
        "name": "PhoneInfoga",
        "mode": "live",
        "status": phoneinfoga_status,
    }

    reputation_engine = {
        "id": "calltracer",
        "name": "CallTracer",
        "mode": "live",
        "status": calltracer_status,
    }

    # ========================================================
    # EVIDENCE
    # ========================================================

    evidence = {
        "technical": {
            "status": "available",
            "confirmed": True,
            "description": (
                "Información técnica del número "
                "obtenida mediante libphonenumber."
            ),
        },

        "osint_queries": {
            "status": (
                "available"
                if public_footprints
                else "none"
            ),
            "count": len(
                public_footprints
            ),
            "confirmed": False,
            "description": (
                "Consultas OSINT disponibles. "
                "No representan coincidencias "
                "confirmadas."
            ),
        },

        "confirmed_matches": {
            "status": "none",
            "count": 0,
            "confirmed": False,
            "description": (
                "NOXIS no confirmó identidad "
                "ni presencia del número en "
                "servicios externos."
            ),
        },

        "reputation": {
            "status": (
                "available"
                if calltracer_available
                else "unavailable"
            ),
            "reported": calltracer_reported,
            "reports_count": calltracer.get(
                "reports_count",
                0,
            ),
            "spam_score": calltracer_spam_score,
            "source": "CallTracer",
            "confirmed_fraud": False,
            "description": (
                "Reputación comunitaria del número "
                "según CallTracer. Los reportes no "
                "confirman por sí solos fraude "
                "ni identidad."
            ),
        },
    }

    # ========================================================
    # RESPONSE
    # ========================================================

    return {
        "input": result.get(
            "input",
            phone_number,
        ),

        "normalized": result.get(
            "normalized",
            {},
        ),

        "validation": result.get(
            "validation",
            {},
        ),

        "country": result.get(
            "country",
            {},
        ),

        "technical": result.get(
            "technical",
            {},
        ),

        "engines": {
            "technical": technical_engine,
            "osint": osint_engine,
            "reputation": reputation_engine,
        },

        "phoneinfoga": phoneinfoga,

        "calltracer": calltracer,

        "public_footprints": (
            public_footprints
        ),

        "footprint_groups": (
            footprint_groups
        ),

        "osint_summary": osint_summary,

        "reputation": reputation,

        "reputation_sources": (
            reputation_sources
        ),

        "reputation_summary": (
            reputation_summary
        ),

        "evidence": evidence,
    }


# ============================================================
# CALLTRACER — ENDPOINT TEMPORAL DE PRUEBA
# ============================================================

@app.post("/api/v1/test/calltracer")
async def calltracer_test(
    request: CallTracerTestRequest,
) -> Dict[str, Any]:

    phone_number = request.phone_number.strip()

    default_region = (
        request.default_region
        or "AR"
    ).strip().upper()

    if not phone_number:
        raise HTTPException(
            status_code=400,
            detail="Número de teléfono requerido",
        )

    try:

        return search_calltracer(
            phone_number=phone_number,
            default_region=default_region,
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Error ejecutando prueba aislada "
                f"de CallTracer: {exc}"
            ),
        ) from exc


# ============================================================
# EMAIL INTELLIGENCE
# ============================================================

@app.post("/api/v1/search/email")
async def email_search(
    request: EmailSearchRequest,
) -> Dict[str, Any]:

    email = (
        request.email
        .strip()
        .lower()
    )

    if not email:
        raise HTTPException(
            status_code=400,
            detail="Correo electrónico requerido",
        )

    # Validación básica.
    # La validación detallada también se realiza
    # en el microservicio Holehe.

    if (
        "@" not in email
        or email.startswith("@")
        or email.endswith("@")
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Formato de correo electrónico inválido"
            ),
        )

    try:

        result = search_holehe(
            email=email
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Error ejecutando Email Intelligence: "
                f"{exc}"
            ),
        ) from exc

    if not isinstance(
        result,
        dict,
    ):

        raise HTTPException(
            status_code=500,
            detail=(
                "Email Intelligence devolvió "
                "un formato inesperado"
            ),
        )

    # ========================================================
    # NORMALIZACIÓN
    # ========================================================

    registered_accounts = result.get(
        "registered_accounts",
        [],
    )

    if not isinstance(
        registered_accounts,
        list,
    ):
        registered_accounts = []

    summary = result.get(
        "summary",
        {},
    )

    if not isinstance(
        summary,
        dict,
    ):
        summary = {}

    # ========================================================
    # EVIDENCE
    # ========================================================

    technical_match = bool(
        registered_accounts
    )

    evidence = {
        "account_presence": {
            "status": (
                "available"
                if technical_match
                else "none"
            ),

            "count": len(
                registered_accounts
            ),

            "technical_match": (
                technical_match
            ),

            "identity_confirmed": False,

            "description": (
                "Holehe detecta presencia técnica "
                "del correo electrónico en servicios "
                "externos. Una coincidencia técnica "
                "no confirma la identidad personal."
            ),
        },

        "confirmed_identity": {
            "status": "none",
            "confirmed": False,

            "description": (
                "NOXIS no confirma automáticamente "
                "que las cuentas detectadas pertenezcan "
                "a una persona específica."
            ),
        },
    }

    # ========================================================
    # RESPONSE
    # ========================================================

    return {
        "input": email,

        "normalized": {
            "email": email,
        },

        "status": result.get(
            "status",
            "unknown",
        ),

        "engine": {
            "id": "holehe",
            "name": "Holehe",
            "mode": "live",
        },

        "service": result.get(
            "service",
            {},
        ),

        # ====================================================
        # DIAGNÓSTICO TEMPORAL
        # ====================================================
        #
        # Permite ver el error interno real de HoleheEngine
        # durante esta fase de integración.
        #
        # No altera el funcionamiento de la búsqueda.
        # Puede retirarse más adelante cuando el flujo quede
        # completamente validado.
        # ====================================================

        "diagnostics": {
            "error": result.get(
                "error"
            ),

            "message": result.get(
                "message"
            ),

            "response": result.get(
                "response"
            ),

            "wakeup": result.get(
                "wakeup"
            ),
        },

        "duration_seconds": result.get(
            "duration_seconds"
        ),

        "summary": summary,

        "registered_accounts": (
            registered_accounts
        ),

        "results": result.get(
            "results",
            [],
        ),

        "evidence": evidence,
    }
