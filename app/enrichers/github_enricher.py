from typing import Any

import httpx

from app.enrichers.base import BaseEnricher


class GitHubEnricher(BaseEnricher):
    service_name = "GitHub"

    API_URL = "https://api.github.com/users/{username}"

    async def enrich(
        self,
        username: str,
        result: dict[str, Any]
    ) -> dict[str, Any]:

        url = self.API_URL.format(username=username)

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "NOXIS-OSINT"
        }

        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True
        ) as client:

            response = await client.get(
                url,
                headers=headers
            )

        if response.status_code == 404:
            return {}

        if response.status_code != 200:
            return {
                "_enrichment_status": "error",
                "_enrichment_http_status": response.status_code
            }

        data = response.json()

        metadata: dict[str, Any] = {}

        field_map = {
            "login": "username",
            "name": "display_name",
            "bio": "bio",
            "location": "location",
            "blog": "website",
            "avatar_url": "avatar_url",
            "html_url": "profile_url",
            "company": "company",
            "public_repos": "public_repositories",
            "followers": "followers",
            "following": "following",
            "created_at": "account_created_at",
            "updated_at": "account_updated_at",
        }

        for source_key, target_key in field_map.items():
            value = data.get(source_key)

            if value not in (None, "", [], {}):
                metadata[target_key] = value

        metadata["_enrichment_status"] = "success"
        metadata["_enrichment_source"] = "github_api"

        return metadata
