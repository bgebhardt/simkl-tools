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
