"""
NOXIS API
=========

Backend principal de NOXIS Intelligence Platform.

Funciones actuales:
- Username Intelligence mediante Maigret
- Enriquecimiento de perfiles
- Phone Intelligence mediante libphonenumber
- Phone OSINT mediante PhoneInfoga
- Consolidación de footprints técnicos
- Separación estricta entre:
    * búsqueda disponible
    * señal técnica
    * coincidencia confirmada

NOXIS no debe interpretar una consulta OSINT generada
como una coincidencia real.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


# ================================================================
# IMPORTS NOXIS
# ================================================================

from app.engines.maigret_engine import analyze_username
from app.engines.phone_engine import analyze_phone


# ================================================================
# APP
# ================================================================

app = FastAPI(
    title="NOXIS API",
    description=(
        "API de inteligencia OSINT para NOXIS. "
        "Integra Username Intelligence, Maigret, "
        "Phone Intelligence y PhoneInfoga."
    ),
    version="0.3.0",
)


# ================================================================
# CORS
# ================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ================================================================
# REQUEST MODELS
# ================================================================

class UsernameSearchRequest(BaseModel):

    username: str = Field(
        ...,
        min_length=1,
        description="Username o alias a investigar.",
    )

    limit: Optional[int] = Field(
        default=None,
        ge=1,
        description=(
            "Cantidad máxima de sitios a consultar. "
            "Si se omite, el motor puede utilizar "
            "su configuración predeterminada."
        ),
    )


class PhoneSearchRequest(BaseModel):

    phone_number: str = Field(
        ...,
        min_length=1,
        description=(
            "Número de teléfono en formato nacional "
            "o internacional."
        ),
    )

    default_region: str = Field(
        default="AR",
        min_length=2,
        max_length=2,
        description=(
            "Código ISO de región utilizado cuando "
            "el número no incluye código internacional."
        ),
    )


# ================================================================
# UTILIDADES
# ================================================================

def _normalize_phone_status(
    phoneinfoga: Dict[str, Any],
) -> str:
    """
    Determina el estado real del motor PhoneInfoga.
    """

    if not isinstance(phoneinfoga, dict):
        return "error"

    status = phoneinfoga.get(
        "status",
        "error",
    )

    if status in (
        "completed",
        "partial",
        "error",
    ):
        return status

    return "unknown"


def _extract_phone_public_footprints(
    phoneinfoga: Dict[str, Any],
) -> list:
    """
    Extrae footprints generados por PhoneInfoga.

    Estos elementos representan búsquedas OSINT disponibles.
    NO deben considerarse coincidencias confirmadas.
    """

    if not isinstance(phoneinfoga, dict):
        return []

    footprints = phoneinfoga.get(
        "public_footprints",
        [],
    )

    if not isinstance(footprints, list):
        return []

    return footprints


def _extract_phone_footprint_groups(
    phoneinfoga: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Extrae grupos de footprints de PhoneInfoga.
    """

    empty_groups = {
        "social_media": [],
        "reputation": [],
        "individuals": [],
        "general": [],
        "disposable_providers": [],
    }

    if not isinstance(phoneinfoga, dict):
        return empty_groups

    groups = phoneinfoga.get(
        "footprint_groups",
        {},
    )

    if not isinstance(groups, dict):
        return empty_groups

    normalized = dict(
        empty_groups
    )

    for key, value in groups.items():

        if isinstance(value, list):
            normalized[key] = value

    return normalized


def _extract_phone_summary(
    phoneinfoga: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Genera un resumen uniforme para el frontend.
    """

    default_summary = {
        "scanners_available": 0,
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

    result = dict(
        default_summary
    )

    result.update(
        summary
    )

    # Por diseño:
    # una búsqueda generada NO equivale a una coincidencia.
    result["confirmed_matches"] = 0

    return result


def _build_phone_reputation(
    footprint_groups: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Resume las fuentes disponibles para investigar reputación.

    IMPORTANTE:
    Esto no determina que un teléfono sea spam, fraude o legítimo.
    Solamente indica que existen consultas OSINT disponibles.
    """

    reputation_items = footprint_groups.get(
        "reputation",
        [],
    )

    if not isinstance(
        reputation_items,
        list,
    ):
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


# ================================================================
# ROOT
# ================================================================

@app.get("/")
async def root() -> Dict[str, Any]:

    return {
        "status": "ok",
        "platform": "NOXIS",
        "version": "0.3.0",
        "services": {
            "username_intelligence": True,
            "phone_intelligence": True,
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
        },
    }


# ================================================================
# HEALTH
# ================================================================

@app.get("/health")
async def health() -> Dict[str, Any]:

    return {
        "status": "ok",
        "platform": "NOXIS",
    }


# ================================================================
# USERNAME INTELLIGENCE
# ================================================================

@app.post("/api/v1/search/username")
async def search_username(
    request: UsernameSearchRequest,
) -> Dict[str, Any]:

    username = request.username.strip()

    if not username:

        raise HTTPException(
            status_code=400,
            detail="Username requerido.",
        )

    try:

        if request.limit is None:

            result = await analyze_username(
                username
            )

        else:

            try:

                result = await analyze_username(
                    username,
                    request.limit,
                )

            except TypeError:
                # Compatibilidad con versiones del motor
                # que solo reciben username.
                result = await analyze_username(
                    username
                )

        return result

    except HTTPException:
        raise

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Error ejecutando Username Intelligence: "
                f"{exc}"
            ),
        )


# ================================================================
# PHONE INTELLIGENCE
# ================================================================

@app.post("/api/v1/search/phone")
async def search_phone(
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
            detail="Número de teléfono requerido.",
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
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Error ejecutando Phone Intelligence: "
                f"{exc}"
            ),
        )

    if not isinstance(
        result,
        dict,
    ):

        raise HTTPException(
            status_code=500,
            detail=(
                "Phone Intelligence devolvió "
                "un formato inesperado."
            ),
        )

    # ============================================================
    # PHONEINFOGA
    # ============================================================

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
        _normalize_phone_status(
            phoneinfoga
        )
    )

    # ============================================================
    # FOOTPRINTS
    # ============================================================

    public_footprints = (
        _extract_phone_public_footprints(
            phoneinfoga
        )
    )

    footprint_groups = (
        _extract_phone_footprint_groups(
            phoneinfoga
        )
    )

    osint_summary = (
        _extract_phone_summary(
            phoneinfoga
        )
    )

    reputation = (
        _build_phone_reputation(
            footprint_groups
        )
    )

    # ============================================================
    # ENGINE STATUS
    # ============================================================

    existing_engines = result.get(
        "engines",
        {},
    )

    if not isinstance(
        existing_engines,
        dict,
    ):
        existing_engines = {}

    technical_engine = existing_engines.get(
        "technical",
        {
            "id": "phonenumbers",
            "name": "Google libphonenumber",
            "mode": "live",
            "status": "completed",
        },
    )

    osint_engine = {
        "id": "phoneinfoga",
        "name": "PhoneInfoga",
        "mode": "live",
        "status": phoneinfoga_status,
    }

    # ============================================================
    # SEPARACIÓN DE EVIDENCIA
    # ============================================================

    evidence = {
        "technical": {
            "status": "available",
            "confirmed": True,
            "description": (
                "Información técnica derivada "
                "de libphonenumber."
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
                "No equivalen a coincidencias confirmadas."
            ),
        },

        "confirmed_matches": {
            "status": "none",
            "count": 0,
            "confirmed": False,
            "description": (
                "NOXIS no confirmó identidades "
                "ni presencia del número en plataformas."
            ),
        },
    }

    # ============================================================
    # RESPONSE CONSOLIDADA
    # ============================================================

    response = {
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
        },

        "phoneinfoga": phoneinfoga,

        # --------------------------------------------------------
        # RESULTADOS CONSOLIDADOS PARA EL FRONTEND
        # --------------------------------------------------------

        "public_footprints": (
            public_footprints
        ),

        "footprint_groups": (
            footprint_groups
        ),

        "osint_summary": (
            osint_summary
        ),

        "reputation": reputation,

        # --------------------------------------------------------
        # CAPA DE EVIDENCIA
        # --------------------------------------------------------

        "evidence": evidence,
    }

    return response


# ================================================================
# API INFORMATION
# ================================================================

@app.get("/api/v1/info")
async def api_info() -> Dict[str, Any]:

    return {
        "platform": "NOXIS",
        "api_version": "0.3.0",

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
        },

        "principles": {
            "technical_match_is_identity": False,
            "search_query_is_confirmation": False,
            "confirmed_identity_required": True,
        },
    }
