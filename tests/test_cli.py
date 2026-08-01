import json
import os
import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from simkl_tools.cli import build_parser, main


BASE_ENV = {
    "SIMKL_CLIENT_ID": "test_id",
    "SIMKL_ACCESS_TOKEN": "test_token",
    "SIMKL_APP_NAME": "simkl-tools",
    "SIMKL_APP_VERSION": "0.1.0",
}


def run_cli(*args, env_overrides=None, expected_exit=0):
    env = {**BASE_ENV, **(env_overrides or {})}
    # Remove keys explicitly set to None so we can simulate missing vars.
    env = {k: v for k, v in env.items() if v is not None}

    stdout_buf = StringIO()
    stderr_buf = StringIO()

    with patch.dict(os.environ, env, clear=True):
        with patch("sys.argv", ["simkl-tools", *args]):
            with patch("sys.stdout", stdout_buf), patch("sys.stderr", stderr_buf):
                try:
                    main()
                except SystemExit as e:
                    if e.code != expected_exit:
                        raise AssertionError(
                            f"Expected exit {expected_exit}, got {e.code}.\n"
                            f"stdout: {stdout_buf.getvalue()!r}\n"
                            f"stderr: {stderr_buf.getvalue()!r}"
                        )

    return stdout_buf.getvalue(), stderr_buf.getvalue()


class TestConfigCheck:
    def test_shows_client_id(self):
        stdout, _ = run_cli("config-check")
        assert "test_id" in stdout

    def test_shows_token_set_yes(self):
        stdout, _ = run_cli("config-check")
        assert "token set:   yes" in stdout

    def test_missing_client_id_exits_nonzero(self):
        with pytest.raises(AssertionError, match="Expected exit 0, got 1"):
            run_cli("config-check", env_overrides={"SIMKL_CLIENT_ID": None})

    def test_missing_client_id_prints_error(self):
        _, stderr = run_cli("config-check", env_overrides={"SIMKL_CLIENT_ID": None}, expected_exit=1)
        assert "SIMKL_CLIENT_ID" in stderr

    def test_missing_token_warns(self):
        stdout, _ = run_cli("config-check", env_overrides={"SIMKL_ACCESS_TOKEN": None})
        assert "NO" in stdout


class TestListCommand:
    def test_calls_all_items_with_correct_args(self):
        with patch("simkl_tools.cli.SimklClient") as MockClient:
            MockClient.return_value.all_items.return_value = {"shows": []}
            run_cli("list", "--type", "shows", "--status", "watching")

        MockClient.return_value.all_items.assert_called_once_with(
            media_type="shows",
            status="watching",
            date_from=None,
            extended="full",
        )

    def test_outputs_json(self):
        with patch("simkl_tools.cli.SimklClient") as MockClient:
            MockClient.return_value.all_items.return_value = {"shows": [{"title": "Test"}]}
            stdout, _ = run_cli("list")

        assert json.loads(stdout) == {"shows": [{"title": "Test"}]}

    def test_missing_token_exits_nonzero(self):
        with pytest.raises(AssertionError, match="Expected exit 0, got 1"):
            run_cli("list", env_overrides={"SIMKL_ACCESS_TOKEN": None})


class TestUpcomingCommand:
    def test_upcoming_enriches_watching_shows_with_episode_dates(self):
        watchlist = {
            "shows": [
                {
                    "status": "watching",
                    "last_watched": "S01E04",
                    "not_aired_episodes_count": 4,
                    "show": {"title": "Star City", "ids": {"simkl": 2437809}},
                }
            ]
        }
        episodes = [
            {"season": 1, "episode": 5, "title": "Bite Your Elbow", "date": "2999-01-01T00:00:00+00:00"},
            {"season": 1, "episode": 6, "title": "Later", "date": "2999-01-10T00:00:00+00:00"},
        ]
        with patch("simkl_tools.cli.datetime") as MockDateTime:
            from datetime import datetime, timezone

            MockDateTime.now.return_value = datetime(2998, 12, 31, 12, 0, tzinfo=timezone.utc)
            MockDateTime.fromisoformat.side_effect = datetime.fromisoformat
            with patch("simkl_tools.cli.SimklClient") as MockClient:
                MockClient.return_value.all_items.return_value = watchlist
                MockClient.return_value.show_episodes.return_value = episodes
                stdout, _ = run_cli("upcoming", "--hours", "24")

        result = json.loads(stdout)
        assert result["items"][0]["show"]["title"] == "Star City"
        assert result["items"][0]["episode"]["episode"] == 5
        MockClient.return_value.all_items.assert_called_once_with(
            media_type="shows",
            status="watching",
            extended="full",
        )
        MockClient.return_value.show_episodes.assert_called_once_with(2437809, extended="full")

    def test_upcoming_skips_shows_without_unaired_by_default(self):
        watchlist = {"shows": [{"not_aired_episodes_count": 0, "show": {"title": "Done", "ids": {"simkl": 1}}}]}
        with patch("simkl_tools.cli.SimklClient") as MockClient:
            MockClient.return_value.all_items.return_value = watchlist
            stdout, _ = run_cli("upcoming")

        assert json.loads(stdout)["items"] == []
        MockClient.return_value.show_episodes.assert_not_called()


class TestProvidersCommand:
    WATCHLIST = {
        "movies": [
            {"movie": {"title": "Fight Club", "ids": {"simkl": 1, "tmdb": 550}}},
            {"movie": {"title": "No TMDB Id", "ids": {"simkl": 2}}},
        ]
    }

    PROVIDERS_RESPONSE = {
        "results": {
            "US": {
                "flatrate": [{"provider_name": "Netflix"}],
                "buy": [{"provider_name": "Apple TV"}],
            }
        }
    }

    def test_calls_all_items_with_movies_and_default_status(self):
        with patch("simkl_tools.cli.SimklClient") as MockClient, patch("simkl_tools.cli.TmdbClient"):
            MockClient.return_value.all_items.return_value = {"movies": []}
            run_cli("providers", env_overrides={"TMDB_API_KEY": "test_key"})

        MockClient.return_value.all_items.assert_called_once_with(media_type="movies", status="plantowatch")

    def test_missing_tmdb_credentials_exits_nonzero(self):
        with patch("simkl_tools.cli.SimklClient") as MockClient:
            MockClient.return_value.all_items.return_value = {"movies": []}
            _, stderr = run_cli("providers", expected_exit=1)

        assert "TMDB" in stderr

    def test_text_output_groups_providers_by_category(self):
        with patch("simkl_tools.cli.SimklClient") as MockClient, patch("simkl_tools.cli.TmdbClient") as MockTmdb:
            MockClient.return_value.all_items.return_value = self.WATCHLIST
            MockTmdb.return_value.watch_providers.return_value = self.PROVIDERS_RESPONSE
            stdout, _ = run_cli("providers", env_overrides={"TMDB_API_KEY": "test_key"})

        assert "Fight Club: flatrate=Netflix | buy=Apple TV" in stdout
        assert "No TMDB Id: No TMDB id on this SIMKL entry" in stdout

    def test_json_output(self):
        with patch("simkl_tools.cli.SimklClient") as MockClient, patch("simkl_tools.cli.TmdbClient") as MockTmdb:
            MockClient.return_value.all_items.return_value = self.WATCHLIST
            MockTmdb.return_value.watch_providers.return_value = self.PROVIDERS_RESPONSE
            stdout, _ = run_cli("providers", "--format", "json", env_overrides={"TMDB_API_KEY": "test_key"})

        result = json.loads(stdout)
        assert result["status"] == "plantowatch"
        assert result["region"] == "US"
        assert result["items"][0]["title"] == "Fight Club"
        assert result["items"][0]["providers"]["flatrate"] == ["Netflix"]
        assert result["items"][1]["error"] == "No TMDB id on this SIMKL entry"

    def test_tmdb_error_reported_per_movie(self):
        with patch("simkl_tools.cli.SimklClient") as MockClient, patch("simkl_tools.cli.TmdbClient") as MockTmdb:
            MockClient.return_value.all_items.return_value = {
                "movies": [{"movie": {"title": "Broken", "ids": {"simkl": 1, "tmdb": 999}}}]
            }
            MockTmdb.return_value.watch_providers.side_effect = RuntimeError("TMDB API error 404: not found")
            stdout, _ = run_cli("providers", env_overrides={"TMDB_API_KEY": "test_key"})

        assert "Broken: TMDB API error 404: not found" in stdout

    def test_custom_status_and_region_passed_through(self):
        with patch("simkl_tools.cli.SimklClient") as MockClient, patch("simkl_tools.cli.TmdbClient"):
            MockClient.return_value.all_items.return_value = {"movies": []}
            run_cli(
                "providers",
                "--status",
                "watching",
                "--region",
                "GB",
                env_overrides={"TMDB_BEARER_TOKEN": "test_bearer"},
            )

        MockClient.return_value.all_items.assert_called_once_with(media_type="movies", status="watching")


class TestDryRunSafety:
    def test_add_to_list_defaults_to_dry_run(self):
        items_json = json.dumps([{"ids": {"simkl": 1}, "type": "movies"}])
        with patch("simkl_tools.cli.SimklClient") as MockClient:
            MockClient.return_value.add_to_list.return_value = {"dry_run": True}
            run_cli("add-to-list", "completed", items_json)

        _, kwargs = MockClient.return_value.add_to_list.call_args
        assert kwargs["dry_run"] is True

    def test_add_to_list_execute_flag_passes_dry_run_false(self):
        items_json = json.dumps([{"ids": {"simkl": 1}, "type": "movies"}])
        with patch("simkl_tools.cli.SimklClient") as MockClient:
            MockClient.return_value.add_to_list.return_value = {"added": 1}
            run_cli("add-to-list", "completed", items_json, "--execute")

        _, kwargs = MockClient.return_value.add_to_list.call_args
        assert kwargs["dry_run"] is False

    def test_move_alias_defaults_to_dry_run(self):
        items_json = json.dumps([{"ids": {"simkl": 1}, "type": "movies"}])
        with patch("simkl_tools.cli.SimklClient") as MockClient:
            MockClient.return_value.add_to_list.return_value = {"dry_run": True}
            run_cli("move", "completed", items_json)

        _, kwargs = MockClient.return_value.add_to_list.call_args
        assert kwargs["dry_run"] is True

    def test_add_history_defaults_to_dry_run(self):
        items_json = json.dumps([{"ids": {"simkl": 1}, "type": "movies"}])
        with patch("simkl_tools.cli.SimklClient") as MockClient:
            MockClient.return_value.add_to_history.return_value = {"dry_run": True}
            run_cli("add-history", items_json)

        _, kwargs = MockClient.return_value.add_to_history.call_args
        assert kwargs["dry_run"] is True

    def test_add_history_execute_flag_passes_dry_run_false(self):
        items_json = json.dumps([{"ids": {"simkl": 1}, "type": "movies"}])
        with patch("simkl_tools.cli.SimklClient") as MockClient:
            MockClient.return_value.add_to_history.return_value = {"added": 1}
            run_cli("add-history", items_json, "--execute")

        _, kwargs = MockClient.return_value.add_to_history.call_args
        assert kwargs["dry_run"] is False

    def test_mark_watched_alias_defaults_to_dry_run(self):
        items_json = json.dumps([{"ids": {"simkl": 1}, "type": "movies"}])
        with patch("simkl_tools.cli.SimklClient") as MockClient:
            MockClient.return_value.add_to_history.return_value = {"dry_run": True}
            run_cli("mark-watched", items_json)

        _, kwargs = MockClient.return_value.add_to_history.call_args
        assert kwargs["dry_run"] is True

    def test_add_to_list_reads_item_json_file(self, tmp_path):
        item_file = tmp_path / "item.json"
        item_file.write_text(json.dumps([{"ids": {"simkl": 1}, "type": "movies"}]))
        with patch("simkl_tools.cli.SimklClient") as MockClient:
            MockClient.return_value.add_to_list.return_value = {"dry_run": True}
            run_cli("add-to-list", "completed", "--item-json", str(item_file))

        args, kwargs = MockClient.return_value.add_to_list.call_args
        assert args[0] == [{"ids": {"simkl": 1}, "type": "movies"}]
        assert kwargs["dry_run"] is True

    def test_add_to_list_dry_run_output_labels_result(self):
        items_json = json.dumps([])
        with patch("simkl_tools.cli.SimklClient") as MockClient:
            MockClient.return_value.add_to_list.return_value = {"dry_run": True, "method": "POST"}
            stdout, _ = run_cli("add-to-list", "watching", items_json)

        assert "[DRY RUN]" in stdout

    def test_add_to_list_execute_output_has_no_dry_run_label(self):
        items_json = json.dumps([])
        with patch("simkl_tools.cli.SimklClient") as MockClient:
            MockClient.return_value.add_to_list.return_value = {"added": 0}
            stdout, _ = run_cli("add-to-list", "watching", items_json, "--execute")

        assert "[DRY RUN]" not in stdout


class TestParserStructure:
    def test_no_subcommand_exits(self):
        with patch("sys.argv", ["simkl-tools"]):
            with pytest.raises(SystemExit):
                build_parser().parse_args()

    def test_move_requires_status_arg(self):
        with patch("sys.argv", ["simkl-tools", "move"]):
            with pytest.raises(SystemExit):
                build_parser().parse_args()
