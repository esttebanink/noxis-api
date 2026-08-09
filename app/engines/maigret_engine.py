import logging
from pathlib import Path
from typing import Any

import maigret
from maigret.checking import maigret as maigret_search
from maigret.sites import MaigretDatabase
from maigret.result import MaigretCheckStatus


logger = logging.getLogger("noxis.maigret")
logger.setLevel(logging.WARNING)


async def search_username(username: str, limit: int = 20) -> dict[str, Any]:
    username = username.strip().lstrip("@")

    if not username:
        raise ValueError("Username vacío")

    maigret_package = Path(maigret.__file__).resolve().parent
    database_path = maigret_package / "resources" / "data.json"

    if not database_path.exists():
        raise FileNotFoundError(
            f"No se encontró data.json en {database_path}"
        )

    database = MaigretDatabase().load_from_path(str(database_path))

    sites = database.ranked_sites_dict(
        top=limit,
        disabled=False,
        id_type="username",
    )

    results = await maigret_search(
        username,
        sites,
        logger,
        timeout=10,
        id_type="username",
        no_progressbar=True,
        max_connections=20,
    )

    normalized = []

    for site_name, result in results.items():
        status_obj = result.get("status")

        if status_obj is None:
            continue

        if status_obj.status == MaigretCheckStatus.CLAIMED:
            status = "found"
        elif status_obj.status == MaigretCheckStatus.AVAILABLE:
            status = "not_found"
        else:
            status = "error"

        normalized.append({
            "site": site_name,
            "username": username,
            "url": result.get("url_user"),
            "status": status,
            "tags": result.get("tags", []),
        })

    found = [
        item for item in normalized
        if item["status"] == "found"
    ]

    return {
        "username": username,
        "engine": "maigret",
        "sites_checked": len(normalized),
        "found": len(found),
        "results": normalized,
    }
