from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/")
async def root():
    return {
        "name": "NOXIS API",
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
            "connected": False
        }
    }
