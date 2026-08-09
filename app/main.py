from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.engines.maigret_engine import search_username


app = FastAPI(
    title="NOXIS API",
    description="Backend de NOXIS OSINT Intelligence Platform",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class UsernameSearchRequest(BaseModel):
    username: str = Field(
        min_length=1,
        max_length=40,
        description="Username o alias a analizar"
    )

    limit: int = Field(
        default=100,
        ge=1,
        le=5000,
        description="Cantidad máxima de servicios a analizar"
    )


@app.get("/")
async def root():
    return {
        "name": "NOXIS API",
        "platform": "NOXIS OSINT Intelligence Platform",
        "version": "Alpha 0.1",
        "status": "online"
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "platform": "NOXIS",
        "engine": {
            "name": "Maigret",
            "connected": True,
            "mode": "live"
        },
        "capabilities": {
            "username_search": True,
            "profile_enrichment": True,
            "max_requested_sites": 5000
        }
    }


@app.post("/api/v1/search/username")
async def username_search(payload: UsernameSearchRequest):
    try:
        username = payload.username.strip().lstrip("@")

        if not username:
            raise HTTPException(
                status_code=400,
                detail="El username no puede estar vacío."
            )

        result = await search_username(
            username=username,
            limit=payload.limit
        )

        return result

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error ejecutando Maigret: {exc}"
        )
