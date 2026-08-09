from pathlib import Path
from typing import Any

import maigret
from maigret.sites import MaigretDatabase


async def search_username(username: str, limit: int = 20) -> dict[str, Any]:
    username = username.strip().lstrip("@")

    if not username:
        raise ValueError("Username vacío")

    # Base de datos incluida dentro del paquete Maigret instalado
    maigret_package = Path(maigret.__file__).resolve().parent
    database_path = maigret_package / "resources" / "data.json"

    if not database_path.exists():
        raise FileNotFoundError(
            f"No se encontró la base de sitios de Maigret en: {database_path}"
        )

    database = MaigretDatabase().load_from_path(str(database_path))

    sites = database.ranked_sites_dict(
        top=limit,
        disabled=False,
        id_type="username",
    )

    results = await maigret.search(
        username=username,
        site_dict=sites,
        timeout=10,
        id_type="username",
    )

    normalized = []

    for site_name, result in results.items():
        status_obj = result.get("status")

        if status_obj is None:
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
        item
        for item in normalized
        if "claimed" in item["status"]
    ]

    return {
        "username": username,
        "engine": "maigret",
        "sites_checked": len(normalized),
        "found": len(found),
        "results": normalized,
    }
