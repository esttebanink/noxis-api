from typing import Any

from app.enrichers.github_enricher import GitHubEnricher


class EnrichmentService:
    """
    Ejecuta enrichers específicos sobre perfiles
    encontrados por los motores OSINT.
    """

    def __init__(self):
        self.enrichers = {
            "GitHub": GitHubEnricher(),
        }

    async def enrich_result(
        self,
        result: dict[str, Any]
    ) -> dict[str, Any]:

        if result.get("status") != "found":
            return result

        site = result.get("site")
        username = result.get("username")

        if not site or not username:
            return result

        enricher = self.enrichers.get(site)

        if enricher is None:
            return result

        try:
            extra_metadata = await enricher.enrich(
                username=username,
                result=result
            )

            existing_metadata = result.get("metadata")

            if not isinstance(existing_metadata, dict):
                existing_metadata = {}

            existing_metadata.update(extra_metadata)

            result["metadata"] = existing_metadata

        except Exception as exc:
            existing_metadata = result.get("metadata")

            if not isinstance(existing_metadata, dict):
                existing_metadata = {}

            existing_metadata["_enrichment_status"] = "error"
            existing_metadata["_enrichment_error"] = str(exc)

            result["metadata"] = existing_metadata

        return result
