import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from simkl_tools.config import TmdbConfig
from simkl_tools.tmdb import BASE_URL, TmdbClient, providers_for_region


def make_config(**overrides) -> TmdbConfig:
    defaults = dict(api_key=None, bearer_token="test_bearer")
    defaults.update(overrides)
    return TmdbConfig(**defaults)


def fake_urlopen(data: dict):
    resp = MagicMock()
    resp.read.return_value = json.dumps(data).encode()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


WATCH_PROVIDERS_RESPONSE = {
    "id": 550,
    "results": {
        "US": {
            "link": "https://www.themoviedb.org/movie/550-fight-club/watch",
            "flatrate": [{"provider_name": "Netflix"}, {"provider_name": "Hulu"}],
            "rent": [{"provider_name": "Apple TV"}],
            "buy": [{"provider_name": "Apple TV"}, {"provider_name": "Amazon Video"}],
        },
        "FR": {
            "free": [{"provider_name": "Pluto TV"}],
        },
    },
}


class TestRequestConstruction:
    def test_watch_providers_url(self):
        client = TmdbClient(make_config())
        with patch("urllib.request.urlopen", return_value=fake_urlopen({})):
            client.watch_providers(550)
            req = urllib.request.urlopen.call_args[0][0]

        assert req.full_url == f"{BASE_URL}/movie/550/watch/providers"

    def test_watch_providers_uses_bearer_auth_when_set(self):
        client = TmdbClient(make_config(bearer_token="test_bearer", api_key=None))
        with patch("urllib.request.urlopen", return_value=fake_urlopen({})):
            client.watch_providers(550)
            req = urllib.request.urlopen.call_args[0][0]

        assert req.get_header("Authorization") == "Bearer test_bearer"
        assert "api_key" not in req.full_url

    def test_watch_providers_uses_api_key_query_param_when_no_bearer(self):
        client = TmdbClient(make_config(bearer_token=None, api_key="test_key"))
        with patch("urllib.request.urlopen", return_value=fake_urlopen({})):
            client.watch_providers(550)
            req = urllib.request.urlopen.call_args[0][0]

        assert req.get_header("Authorization") is None
        assert "api_key=test_key" in req.full_url

    def test_watch_providers_prefers_bearer_over_api_key(self):
        client = TmdbClient(make_config(bearer_token="test_bearer", api_key="test_key"))
        with patch("urllib.request.urlopen", return_value=fake_urlopen({})):
            client.watch_providers(550)
            req = urllib.request.urlopen.call_args[0][0]

        assert req.get_header("Authorization") == "Bearer test_bearer"
        assert "api_key" not in req.full_url


class TestValidation:
    def test_watch_providers_requires_movie_id(self):
        client = TmdbClient(make_config())
        with pytest.raises(ValueError, match="movie_id is required"):
            client.watch_providers("")


class TestErrorHandling:
    def test_http_error_raises_runtime_error(self):
        client = TmdbClient(make_config())
        error = urllib.error.HTTPError(
            url="", code=404, msg="Not Found", hdrs=None, fp=MagicMock(read=lambda: b'{"status_message": "not found"}')
        )
        with patch("urllib.request.urlopen", side_effect=error):
            with pytest.raises(RuntimeError, match="TMDB API error 404"):
                client.watch_providers(550)


class TestProvidersForRegion:
    def test_groups_categories_present_for_region(self):
        grouped = providers_for_region(WATCH_PROVIDERS_RESPONSE, "US")

        assert grouped["flatrate"] == ["Netflix", "Hulu"]
        assert grouped["rent"] == ["Apple TV"]
        assert grouped["buy"] == ["Apple TV", "Amazon Video"]
        assert "ads" not in grouped
        assert "free" not in grouped

    def test_omits_empty_categories(self):
        grouped = providers_for_region(WATCH_PROVIDERS_RESPONSE, "FR")

        assert grouped == {"free": ["Pluto TV"]}

    def test_missing_region_returns_empty_dict(self):
        grouped = providers_for_region(WATCH_PROVIDERS_RESPONSE, "DE")

        assert grouped == {}

    def test_missing_results_key_returns_empty_dict(self):
        grouped = providers_for_region({}, "US")

        assert grouped == {}
