from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.engines.maigret_engine import search_username
from app.engines.phone_engine import analyze_phone


# ==========================================================
# NOXIS API
# ==========================================================

app = FastAPI(
    title="NOXIS API",
    description="Backend de NOXIS OSINT Intelligence Platform",
    version="0.2.0",
)


# ==========================================================
# CORS
# ==========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ==========================================================
# MODELOS
# ==========================================================

class UsernameSearchRequest(BaseModel):
    username: str = Field(
        min_length=1,
        max_length=40,
        description="Username o alias a analizar",
    )

    limit: int = Field(
        default=100,
        ge=1,
        le=5000,
        description="Cantidad máxima de servicios a analizar",
    )


class PhoneSearchRequest(BaseModel):
    phone_number: str = Field(
        min_length=3,
        max_length=40,
        description=(
            "Número telefónico en formato nacional "
            "o internacional"
        ),
    )

    default_region: str = Field(
        default="AR",
        min_length=2,
        max_length=2,
        description=(
            "Código ISO de región utilizado cuando "
            "el número no incluye prefijo internacional"
        ),
    )


# ==========================================================
# ROOT
# ==========================================================

@app.get("/")
async def root():
    return {
        "name": "NOXIS API",
        "platform": "NOXIS OSINT Intelligence Platform",
        "version": "Alpha 0.2",
        "status": "online",
        "engines": [
            {
                "id": "maigret",
                "name": "Maigret",
                "capability": "username_intelligence",
                "status": "available",
            },
            {
                "id": "phonenumbers",
                "name": "Google libphonenumber",
                "capability": "phone_intelligence",
                "status": "available",
            },
        ],
    }


# ==========================================================
# HEALTH
# ==========================================================

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "platform": "NOXIS",
        "version": "Alpha 0.2",
        "engines": {
            "maigret": {
                "name": "Maigret",
                "connected": True,
                "mode": "live",
            },
            "phone": {
                "name": "Google libphonenumber",
                "connected": True,
                "mode": "live",
            },
        },
        "capabilities": {
            "username_search": True,
            "profile_enrichment": True,
            "phone_intelligence": True,
            "phone_normalization": True,
            "phone_validation": True,
            "phone_region_analysis": True,
            "phone_carrier_analysis": True,
            "phone_line_type_analysis": True,
            "phone_public_footprints": False,
            "phone_reputation": False,
            "max_requested_sites": 5000,
        },
    }


# ==========================================================
# USERNAME INTELLIGENCE
# ==========================================================

@app.post("/api/v1/search/username")
async def username_search(payload: UsernameSearchRequest):
    try:
        username = payload.username.strip().lstrip("@")

        if not username:
            raise HTTPException(
                status_code=400,
                detail="El username no puede estar vacío.",
            )

        result = await search_username(
            username=username,
            limit=payload.limit,
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
            detail=f"Error ejecutando Maigret: {exc}",
        )


# ==========================================================
# PHONE INTELLIGENCE
# ==========================================================

@app.post("/api/v1/search/phone")
async def phone_search(payload: PhoneSearchRequest):
    try:
        phone_number = payload.phone_number.strip()
        default_region = payload.default_region.strip().upper()

        if not phone_number:
            raise HTTPException(
                status_code=400,
                detail="El número de teléfono no puede estar vacío.",
            )

        if (
            len(default_region) != 2
            or not default_region.isalpha()
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "default_region debe ser un código ISO "
                    "de dos letras. Ejemplo: AR."
                ),
            )

        result = await analyze_phone(
            phone_number=phone_number,
            default_region=default_region,
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
            detail=f"Error ejecutando Phone Intelligence: {exc}",
        )
