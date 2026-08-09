import logging
import time
from pathlib import Path
from typing import Any

import maigret
from maigret.checking import maigret as maigret_search
from maigret.sites import MaigretDatabase
from maigret.result import MaigretCheckStatus


logger = logging.getLogger("noxis.maigret")
logger.setLevel(logging.WARNING)


async def search_username(username: str, limit: int = 20) -> dict[str, Any]:
    started_at = time.perf_counter()

    username = username.strip().lstrip("@")

    if not username:
        raise ValueError("Username vacío")

    # Base de datos oficial incluida en el paquete Maigret
    maigret_package = Path(maigret.__file__).resolve().parent
    database_path = maigret_package / "resources" / "data.json"

    if not database_path.exists():
        raise FileNotFoundError(
            f"No se encontró data.json en {database_path}"
        )

    database = MaigretDatabase().load_from_path(str(database_path))

    # Maigret puede agregar mirrors además del top solicitado.
    ranked_sites = database.ranked_sites_dict(
        top=limit,
        disabled=False,
        id_type="username",
    )

    # NOXIS aplica un límite estricto para controlar recursos.
    sites = dict(list(ranked_sites.items())[:limit])

    results = await maigret_search(
        username,
        sites,
        logger,
        timeout=10,
        id_type="username",
        no_progressbar=True,
        max_connections=min(limit, 20),
    )

    normalized = []

    found_count = 0
    not_found_count = 0
    error_count = 0

    for site_name, result in results.items():
        status_obj = result.get("status")

        if status_obj is None:
            status = "error"
            error_count += 1

        elif status_obj.status == MaigretCheckStatus.CLAIMED:
            status = "found"
            found_count += 1

        elif status_obj.status == MaigretCheckStatus.AVAILABLE:
            status = "not_found"
            not_found_count += 1

        else:
            status = "error"
            error_count += 1

        site_info = sites.get(site_name)

        category = "Otros"
        tags = result.get("tags", [])

        if site_info:
            site_tags = getattr(site_info, "tags", None)

            if site_tags:
                tags = list(site_tags)

        normalized.append(
            {
                "site": site_name,
                "username": username,
                "url": result.get("url_user"),
                "status": status,
                "category": category,
                "tags": tags,
            }
        )

    duration = round(time.perf_counter() - started_at, 2)

    return {
        "username": username,
        "engine": {
            "id": "maigret",
            "name": "Maigret",
            "mode": "live",
        },
        "status": "completed",
        "requested_limit": limit,
        "sites_checked": len(normalized),
        "summary": {
            "found": found_count,
            "not_found": not_found_count,
            "errors": error_count,
            "total": len(normalized),
        },
        "duration_seconds": duration,
        "results": normalized,
    }
