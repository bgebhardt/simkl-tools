import argparse
import json
import sys

from .client import VALID_MEDIA_TYPES, VALID_STATUSES, SimklClient
from .config import load_config


def cmd_config_check(args: argparse.Namespace) -> None:
    try:
        cfg = load_config(require_token=False)
    except ValueError as e:
        print(f"Config error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"client_id:   {cfg.client_id}")
    print(f"app_name:    {cfg.app_name}")
    print(f"app_version: {cfg.app_version}")
    if cfg.access_token:
        print("token set:   yes")
    else:
        print("token set:   NO (authenticated operations will fail)")


def cmd_list(args: argparse.Namespace) -> None:
    try:
        cfg = load_config(require_token=True)
    except ValueError as e:
        print(f"Config error: {e}", file=sys.stderr)
        sys.exit(1)

    client = SimklClient(cfg)
    try:
        result = client.all_items(
            media_type=args.type,
            status=args.status,
            date_from=args.date_from,
            extended=args.extended,
        )
    except (ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, indent=2))


def _load_items_json(*, item_json: str | None = None, item_json_file: str | None = None) -> list:
    if item_json_file:
        try:
            with open(item_json_file, encoding="utf-8") as f:
                raw = f.read()
        except OSError as e:
            print(f"Unable to read --item-json file: {e}", file=sys.stderr)
            sys.exit(1)
    elif item_json:
        raw = item_json
    else:
        print("Provide items as ITEMS_JSON or --item-json FILE", file=sys.stderr)
        sys.exit(1)

    try:
        items = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON for items: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(items, list):
        print("items JSON must be an array", file=sys.stderr)
        sys.exit(1)
    return items


def cmd_add_to_list(args: argparse.Namespace) -> None:
    execute = getattr(args, "execute", False)
    dry_run = not execute

    try:
        cfg = load_config(require_token=True)
    except ValueError as e:
        print(f"Config error: {e}", file=sys.stderr)
        sys.exit(1)

    items = _load_items_json(item_json=getattr(args, "items_json", None), item_json_file=args.item_json)

    client = SimklClient(cfg)
    try:
        result = client.add_to_list(items, args.status, dry_run=dry_run)
    except (ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if dry_run:
        print("[DRY RUN] Would send:")
    print(json.dumps(result, indent=2))


def cmd_add_history(args: argparse.Namespace) -> None:
    execute = getattr(args, "execute", False)
    dry_run = not execute

    try:
        cfg = load_config(require_token=True)
    except ValueError as e:
        print(f"Config error: {e}", file=sys.stderr)
        sys.exit(1)

    items = _load_items_json(item_json=getattr(args, "items_json", None), item_json_file=args.item_json)

    client = SimklClient(cfg)
    try:
        result = client.add_to_history(items, dry_run=dry_run)
    except (ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if dry_run:
        print("[DRY RUN] Would send:")
    print(json.dumps(result, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="simkl-tools",
        description="Local CLI for inspecting and managing SIMKL watchlists",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("config-check", help="Verify that required env vars are set")

    p_list = sub.add_parser("list", help="List items from your SIMKL watchlist")
    p_list.add_argument(
        "--type",
        choices=sorted(VALID_MEDIA_TYPES),
        default="shows",
        metavar="TYPE",
        help=f"Media type: {sorted(VALID_MEDIA_TYPES)} (default: shows)",
    )
    p_list.add_argument(
        "--status",
        choices=sorted(VALID_STATUSES),
        default="watching",
        metavar="STATUS",
        help=f"Watchlist status: {sorted(VALID_STATUSES)} (default: watching)",
    )
    p_list.add_argument(
        "--date-from",
        dest="date_from",
        metavar="YYYY-MM-DDTHH:MM:SSZ",
        help="Only return items updated after this date",
    )
    p_list.add_argument(
        "--extended",
        default="full",
        help="Extended info level (default: full)",
    )

    p_add_list = sub.add_parser(
        "add-to-list",
        aliases=["move"],
        help="Move item(s) to a different watchlist status",
    )
    p_add_list.add_argument(
        "status",
        choices=sorted(VALID_STATUSES),
        metavar="STATUS",
        help=f"Target status: {sorted(VALID_STATUSES)}",
    )
    p_add_list.add_argument(
        "items_json",
        nargs="?",
        metavar="ITEMS_JSON",
        help='JSON array of items, e.g. \'[{"ids":{"simkl":12345},"type":"shows"}]\'',
    )
    p_add_list.add_argument(
        "--item-json",
        metavar="FILE",
        help="Read JSON array of items from FILE",
    )
    p_add_list.add_argument(
        "--execute",
        action="store_true",
        help="Actually send the request (default is dry-run — prints what would be sent)",
    )

    p_history = sub.add_parser(
        "add-history",
        aliases=["mark-watched"],
        help="Add item(s) to watch history via POST /sync/history",
    )
    p_history.add_argument(
        "items_json",
        nargs="?",
        metavar="ITEMS_JSON",
        help='JSON array of items, e.g. \'[{"ids":{"simkl":12345},"type":"movies"}]\'',
    )
    p_history.add_argument(
        "--item-json",
        metavar="FILE",
        help="Read JSON array of items from FILE",
    )
    p_history.add_argument(
        "--execute",
        action="store_true",
        help="Actually send the request (default is dry-run — prints what would be sent)",
    )

    return parser


_DISPATCH = {
    "config-check": cmd_config_check,
    "list": cmd_list,
    "add-to-list": cmd_add_to_list,
    "move": cmd_add_to_list,
    "add-history": cmd_add_history,
    "mark-watched": cmd_add_history,
}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _DISPATCH[args.command](args)


if __name__ == "__main__":
    main()
