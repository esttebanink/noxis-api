from typing import Any

from maigret import maigret
from maigret.sites import MaigretDatabase


async def search_username(username: str, limit: int = 50) -> dict[str, Any]:
    username = username.strip().lstrip("@")

    if not username:
        raise ValueError("Username vacío")

    database = MaigretDatabase().load_from_path()

    sites = dict(
        list(database.ranked_sites_dict().items())[:limit]
    )

    results = await maigret(
        username=username,
        site_dict=sites,
        timeout=10
    )

    normalized = []

    for site_name, result in results.items():
        status_obj = result.get("status")

        if not status_obj:
            continue

        status = str(status_obj.status).lower()

        normalized.append({
            "site": site_name,
            "username": username,
            "url": result.get("url_user"),
            "status": status,
            "tags": result.get("tags", []),
        })

    found = [
        item for item in normalized
        if "claimed" in item["status"]
    ]

    return {
        "username": username,
        "engine": "maigret",
        "sites_checked": len(normalized),
        "found": len(found),
        "results": normalized,
    }
