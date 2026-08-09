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


def make_json_safe(value: Any) -> Any:
    """
    Convierte valores extraídos por Maigret en estructuras
    seguras para devolver mediante JSON.
    """
    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, list):
        return [
            make_json_safe(item)
            for item in value
            if make_json_safe(item) is not None
        ]

    if isinstance(value, tuple):
        return [
            make_json_safe(item)
            for item in value
            if make_json_safe(item) is not None
        ]

    if isinstance(value, set):
        return [
            make_json_safe(item)
            for item in value
            if make_json_safe(item) is not None
        ]

    if isinstance(value, dict):
        return {
            str(key): make_json_safe(item)
            for key, item in value.items()
            if make_json_safe(item) is not None
        }

    return str(value)


def extract_metadata(result: dict) -> dict[str, Any]:
    """
    Extrae metadata pública obtenida realmente por Maigret.

    Maigret guarda ids_data principalmente dentro del
    objeto status. También puede devolver ids_links e
    ids_usernames en el resultado general.
    """
    metadata: dict[str, Any] = {}

    status_obj = result.get("status")

    if status_obj is not None:
        ids_data = getattr(status_obj, "ids_data", None)

        if isinstance(ids_data, dict):
            for key, value in ids_data.items():
                safe_value = make_json_safe(value)

                if safe_value not in (None, "", [], {}):
                    metadata[str(key)] = safe_value

    ids_links = result.get("ids_links")

    if ids_links:
        safe_links = make_json_safe(ids_links)

        if safe_links not in (None, "", [], {}):
            metadata["links"] = safe_links

    ids_usernames = result.get("ids_usernames")

    if ids_usernames:
        safe_usernames = make_json_safe(ids_usernames)

        if safe_usernames not in (None, "", [], {}):
            metadata["usernames"] = safe_usernames

    return metadata


def classify_category(tags: list[str]) -> str:
    normalized_tags = {
        str(tag).strip().lower()
        for tag in tags
    }

    if "coding" in normalized_tags:
        return "Desarrollo"

    if "professional" in normalized_tags:
        return "Profesional"

    if "messaging" in normalized_tags:
        return "Mensajería"

    if "gaming" in normalized_tags or "game" in normalized_tags:
        return "Gaming"

    if "forum" in normalized_tags or "discussion" in normalized_tags:
        return "Foros"

    if "social" in normalized_tags:
        return "Red social"

    if (
        "video" in normalized_tags
        or "photo" in normalized_tags
        or "music" in normalized_tags
        or "art" in normalized_tags
        or "blog" in normalized_tags
    ):
        return "Contenido"

    return "Otros"


async def search_username(
    username: str,
    limit: int = 20
) -> dict[str, Any]:

    started_at = time.perf_counter()

    username = username.strip().lstrip("@")

    if not username:
        raise ValueError("Username vacío")

    # --------------------------------------------------
    # BASE DE DATOS MAIGRET
    # --------------------------------------------------

    maigret_package = Path(maigret.__file__).resolve().parent
    database_path = maigret_package / "resources" / "data.json"

    if not database_path.exists():
        raise FileNotFoundError(
            f"No se encontró data.json en {database_path}"
        )

    database = MaigretDatabase().load_from_path(
        str(database_path)
    )

    # --------------------------------------------------
    # SELECCIÓN DE SERVICIOS
    # --------------------------------------------------

    ranked_sites = database.ranked_sites_dict(
        top=limit,
        disabled=False,
        id_type="username",
    )

    sites = dict(
        list(ranked_sites.items())[:limit]
    )

    # --------------------------------------------------
    # BÚSQUEDA + PARSING + ENRICH
    # --------------------------------------------------

    results = await maigret_search(
        username,
        sites,
        logger,
        timeout=10,
        id_type="username",
        no_progressbar=True,
        max_connections=min(limit, 20),
        is_parsing_enabled=True,
        is_enrich_enabled=True,
    )

    # --------------------------------------------------
    # NORMALIZACIÓN
    # --------------------------------------------------

    normalized_results = []

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

        # --------------------------------------------------
        # TAGS
        # --------------------------------------------------

        tags = result.get("tags", [])

        if not isinstance(tags, list):
            tags = []

        site_info = sites.get(site_name)

        if site_info:
            site_tags = getattr(site_info, "tags", None)

            if site_tags:
                tags = list(site_tags)

        category = classify_category(tags)

        # --------------------------------------------------
        # METADATA
        # --------------------------------------------------

        metadata = extract_metadata(result)

        normalized_results.append(
            {
                "site": site_name,
                "username": username,
                "url": result.get("url_user"),
                "status": status,
                "category": category,
                "tags": tags,
                "metadata": metadata,
            }
        )

    duration = round(
        time.perf_counter() - started_at,
        2
    )

    return {
        "username": username,

        "engine": {
            "id": "maigret",
            "name": "Maigret",
            "mode": "live",
        },

        "status": "completed",

        "requested_limit": limit,

        "sites_checked": len(normalized_results),

        "summary": {
            "found": found_count,
            "not_found": not_found_count,
            "errors": error_count,
            "total": len(normalized_results),
        },

        "duration_seconds": duration,

        "results": normalized_results,
    }
