import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .config import Config

BASE_URL = "https://api.simkl.com"

VALID_MEDIA_TYPES = frozenset({"movies", "shows", "anime"})
VALID_STATUSES = frozenset({"watching", "plantowatch", "hold", "completed", "dropped"})
VALID_EPISODE_MEDIA_TYPES = frozenset({"shows"})


class SimklClient:
    def __init__(self, config: Config) -> None:
        self.config = config

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        body: Any = None,
        require_auth: bool = False,
    ) -> Any:
        base_params: dict[str, str] = {
            "client_id": self.config.client_id,
            "app-name": self.config.app_name,
            "app-version": self.config.app_version,
        }
        if params:
            base_params.update(params)

        url = f"{BASE_URL}{path}?{urllib.parse.urlencode(base_params)}"

        headers: dict[str, str] = {
            "User-Agent": f"{self.config.app_name}/{self.config.app_version}",
            "Content-Type": "application/json",
        }
        if require_auth:
            if not self.config.access_token:
                raise ValueError("Access token required but SIMKL_ACCESS_TOKEN is not set")
            headers["Authorization"] = f"Bearer {self.config.access_token}"

        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode(errors="replace")
            raise RuntimeError(f"SIMKL API error {e.code}: {error_body}") from e

    def all_items(
        self,
        media_type: str,
        status: str,
        date_from: str | None = None,
        extended: str = "full",
    ) -> dict:
        if media_type not in VALID_MEDIA_TYPES:
            raise ValueError(f"Invalid media_type {media_type!r}; choose from {sorted(VALID_MEDIA_TYPES)}")
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status {status!r}; choose from {sorted(VALID_STATUSES)}")

        params: dict[str, str] = {"extended": extended}
        if date_from:
            params["date_from"] = date_from

        return self._request(
            "GET",
            f"/sync/all-items/{media_type}/{status}",
            params=params,
            require_auth=True,
        )

    def show_episodes(self, simkl_id: int | str, extended: str = "full") -> list:
        """Return episode metadata for a show by SIMKL ID.

        Calls GET /tv/episodes/{simkl_id}. SIMKL includes episode air dates
        here even when /sync/all-items only reports not_aired_episodes_count.
        """
        if not simkl_id:
            raise ValueError("simkl_id is required")

        return self._request(
            "GET",
            f"/tv/episodes/{simkl_id}",
            params={"extended": extended},
            require_auth=False,
        )

    def add_to_list(
        self,
        items: list[dict],
        target_status: str,
        *,
        dry_run: bool = True,
    ) -> dict:
        if target_status not in VALID_STATUSES:
            raise ValueError(f"Invalid target_status {target_status!r}; choose from {sorted(VALID_STATUSES)}")

        # Group items by media type for the SIMKL bulk payload format.
        # SIMKL requires the destination as a per-item `to` field; the legacy
        # top-level `to`/`list` shape is rejected by the API.
        payload: dict[str, list] = {"movies": [], "shows": [], "anime": []}
        for item in items:
            media_type = item.get("type", "movies")
            if media_type not in payload:
                payload[media_type] = []
            # Strip synthetic "type" key before sending; SIMKL doesn't want it.
            entry = {k: v for k, v in item.items() if k != "type"}
            entry["to"] = target_status
            payload[media_type].append(entry)

        body = payload
        planned = {
            "dry_run": True,
            "method": "POST",
            "url": f"{BASE_URL}/sync/add-to-list",
            "body": body,
        }

        if dry_run:
            return planned

        return self._request("POST", "/sync/add-to-list", body=body, require_auth=True)

    def add_to_history(
        self,
        items: list[dict],
        *,
        dry_run: bool = True,
    ) -> dict:
        payload: dict[str, list] = {"movies": [], "shows": [], "anime": []}
        for item in items:
            media_type = item.get("type", "movies")
            if media_type not in payload:
                payload[media_type] = []
            entry = {k: v for k, v in item.items() if k != "type"}
            payload[media_type].append(entry)

        planned = {
            "dry_run": True,
            "method": "POST",
            "url": f"{BASE_URL}/sync/history",
            "body": payload,
        }

        if dry_run:
            return planned

        return self._request("POST", "/sync/history", body=payload, require_auth=True)
