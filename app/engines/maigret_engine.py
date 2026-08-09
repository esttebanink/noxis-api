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


def clean_metadata(result: dict) -> dict[str, Any]:
    metadata: dict[str, Any] = {}

    raw = result.get("ids_data")

    if isinstance(raw, dict):
        for key, value in raw.items():
            if value in (None, "", [], {}):
                continue

            if isinstance(value, (str, int, float, bool)):
                metadata[key] = value

            elif isinstance(value, list):
                metadata[key] = [
                    item
                    for item in value
                    if isinstance(item, (str, int, float, bool))
                ]

    return metadata


async def search_username(username: str, limit: int = 20) -> dict[str, Any]:
    started_at = time.perf_counter()

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

    ranked_sites = database.ranked_sites_dict(
        top=limit,
        disabled=False,
        id_type="username",
    )

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

        tags = result.get("tags", [])

        if site_info:
            site_tags = getattr(site_info, "tags", None)

            if site_tags:
                tags = list(site_tags)

        metadata = clean_metadata(result)

        normalized.append({
            "site": site_name,
            "username": username,
            "url": result.get("url_user"),
            "status": status,
            "category": "Otros",
            "tags": tags,
            "metadata": metadata,
        })

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
