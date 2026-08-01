import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .config import TmdbConfig

BASE_URL = "https://api.themoviedb.org/3"

PROVIDER_CATEGORIES = ("flatrate", "ads", "free", "rent", "buy")


class TmdbClient:
    def __init__(self, config: TmdbConfig) -> None:
        self.config = config

    def _request(self, method: str, path: str, *, params: dict[str, str] | None = None) -> Any:
        query: dict[str, str] = dict(params or {})
        headers: dict[str, str] = {"Content-Type": "application/json"}

        # Prefer bearer auth (v4 read access token) over the api_key query param
        # when both are set, matching TMDB's own auth precedence.
        if self.config.bearer_token:
            headers["Authorization"] = f"Bearer {self.config.bearer_token}"
        elif self.config.api_key:
            query["api_key"] = self.config.api_key

        url = f"{BASE_URL}{path}"
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"

        req = urllib.request.Request(url, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode(errors="replace")
            raise RuntimeError(f"TMDB API error {e.code}: {error_body}") from e

    def watch_providers(self, movie_id: int | str) -> dict:
        if not movie_id:
            raise ValueError("movie_id is required")

        return self._request("GET", f"/movie/{movie_id}/watch/providers")


def providers_for_region(watch_providers_response: dict, region: str) -> dict[str, list[str]]:
    """Group a /movie/{id}/watch/providers response into category -> provider names for one region."""
    region_data = watch_providers_response.get("results", {}).get(region, {})

    grouped: dict[str, list[str]] = {}
    for category in PROVIDER_CATEGORIES:
        names = [p.get("provider_name") for p in region_data.get(category) or [] if p.get("provider_name")]
        if names:
            grouped[category] = names

    return grouped
