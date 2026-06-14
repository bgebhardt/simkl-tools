import json
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from simkl_tools.client import BASE_URL, SimklClient
from simkl_tools.config import Config


def make_config(**overrides) -> Config:
    defaults = dict(
        client_id="test_client_id",
        access_token="test_token",
        app_name="simkl-tools",
        app_version="0.1.0",
    )
    defaults.update(overrides)
    return Config(**defaults)


def fake_urlopen(data: dict):
    resp = MagicMock()
    resp.read.return_value = json.dumps(data).encode()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestRequestConstruction:
    def test_all_items_url_contains_client_id(self):
        client = SimklClient(make_config())
        with patch("urllib.request.urlopen", return_value=fake_urlopen({})):
            client.all_items("movies", "watching")
            req = urllib.request.urlopen.call_args[0][0]

        assert "client_id=test_client_id" in req.full_url
        assert "/sync/all-items/movies/watching" in req.full_url

    def test_all_items_adds_app_params(self):
        client = SimklClient(make_config())
        with patch("urllib.request.urlopen", return_value=fake_urlopen({})):
            client.all_items("shows", "plantowatch")
            req = urllib.request.urlopen.call_args[0][0]

        assert "app-name=simkl-tools" in req.full_url
        assert "app-version=0.1.0" in req.full_url

    def test_all_items_adds_date_from(self):
        client = SimklClient(make_config())
        with patch("urllib.request.urlopen", return_value=fake_urlopen({})):
            client.all_items("shows", "watching", date_from="2024-01-01T00:00:00Z")
            req = urllib.request.urlopen.call_args[0][0]

        assert "date_from=2024-01-01" in req.full_url

    def test_all_items_sets_bearer_auth_header(self):
        client = SimklClient(make_config())
        with patch("urllib.request.urlopen", return_value=fake_urlopen({})):
            client.all_items("movies", "completed")
            req = urllib.request.urlopen.call_args[0][0]

        assert req.get_header("Authorization") == "Bearer test_token"

    def test_all_items_sets_user_agent(self):
        client = SimklClient(make_config())
        with patch("urllib.request.urlopen", return_value=fake_urlopen({})):
            client.all_items("movies", "completed")
            req = urllib.request.urlopen.call_args[0][0]

        assert req.get_header("User-agent") == "simkl-tools/0.1.0"


class TestValidation:
    def test_all_items_invalid_media_type_raises(self):
        client = SimklClient(make_config())
        with pytest.raises(ValueError, match="Invalid media_type"):
            client.all_items("books", "watching")

    def test_all_items_invalid_status_raises(self):
        client = SimklClient(make_config())
        with pytest.raises(ValueError, match="Invalid status"):
            client.all_items("movies", "someday")

    def test_add_to_list_invalid_status_raises(self):
        client = SimklClient(make_config())
        with pytest.raises(ValueError, match="Invalid target_status"):
            client.add_to_list([], "wishlist", dry_run=True)


class TestMissingConfig:
    def test_no_token_raises_on_authenticated_request(self):
        client = SimklClient(make_config(access_token=None))
        with pytest.raises(ValueError, match="Access token required"):
            client._request("GET", "/sync/all-items/movies/watching", require_auth=True)

    def test_no_token_does_not_raise_on_dry_run(self):
        client = SimklClient(make_config(access_token=None))
        result = client.add_to_list([], "plantowatch", dry_run=True)
        assert result["dry_run"] is True


class TestDryRun:
    def test_add_to_list_dry_run_does_not_call_network(self):
        client = SimklClient(make_config())
        with patch("urllib.request.urlopen") as mock_open:
            client.add_to_list([{"ids": {"simkl": 1}, "type": "movies"}], "completed", dry_run=True)

        mock_open.assert_not_called()

    def test_add_to_history_dry_run_does_not_call_network(self):
        client = SimklClient(make_config())
        with patch("urllib.request.urlopen") as mock_open:
            client.add_to_history([{"ids": {"simkl": 1}, "type": "shows"}], dry_run=True)

        mock_open.assert_not_called()

    def test_add_to_list_dry_run_returns_planned_post(self):
        client = SimklClient(make_config())
        result = client.add_to_list([], "watching", dry_run=True)

        assert result["dry_run"] is True
        assert result["method"] == "POST"
        assert "/sync/add-to-list" in result["url"]

    def test_add_to_history_dry_run_returns_planned_post(self):
        client = SimklClient(make_config())
        result = client.add_to_history([], dry_run=True)

        assert result["dry_run"] is True
        assert result["method"] == "POST"
        assert "/sync/history" in result["url"]

    def test_add_to_list_dry_run_groups_items_by_type(self):
        client = SimklClient(make_config())
        items = [
            {"ids": {"simkl": 1}, "type": "movies"},
            {"ids": {"simkl": 2}, "type": "shows"},
            {"ids": {"simkl": 3}, "type": "movies"},
        ]
        result = client.add_to_list(items, "completed", dry_run=True)

        assert len(result["body"]["movies"]) == 2
        assert len(result["body"]["shows"]) == 1

    def test_add_to_list_dry_run_strips_type_key_from_items(self):
        client = SimklClient(make_config())
        items = [{"ids": {"simkl": 42}, "type": "movies"}]
        result = client.add_to_list(items, "plantowatch", dry_run=True)

        sent_item = result["body"]["movies"][0]
        assert "type" not in sent_item
        assert sent_item["ids"]["simkl"] == 42

    def test_add_to_list_dry_run_includes_target_status_per_item(self):
        client = SimklClient(make_config())
        result = client.add_to_list([{"ids": {"simkl": 42}, "type": "movies"}], "dropped", dry_run=True)

        assert "list" not in result["body"]
        assert result["body"]["movies"][0]["to"] == "dropped"

    def test_add_to_list_execute_calls_network(self):
        client = SimklClient(make_config())
        with patch("urllib.request.urlopen", return_value=fake_urlopen({"added": 1})) as mock_open:
            result = client.add_to_list([], "completed", dry_run=False)

        mock_open.assert_called_once()
        assert result == {"added": 1}
