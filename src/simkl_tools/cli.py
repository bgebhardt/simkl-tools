import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

from .client import VALID_MEDIA_TYPES, VALID_STATUSES, SimklClient
from .config import load_config, load_tmdb_config
from .tmdb import TmdbClient, providers_for_region


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



def _parse_simkl_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def cmd_upcoming(args: argparse.Namespace) -> None:
    try:
        cfg = load_config(require_token=True)
    except ValueError as e:
        print(f"Config error: {e}", file=sys.stderr)
        sys.exit(1)

    client = SimklClient(cfg)
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(hours=args.hours)
    include_past_since = now - timedelta(hours=args.past_hours)

    try:
        watchlist = client.all_items(
            media_type="shows",
            status=args.status,
            extended=args.extended,
        )
    except (ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    upcoming: list[dict] = []
    for item in watchlist.get("shows", []):
        show = item.get("show", {})
        simkl_id = show.get("ids", {}).get("simkl")
        if not simkl_id:
            continue
        if not args.all and not item.get("not_aired_episodes_count"):
            continue

        try:
            episodes = client.show_episodes(simkl_id, extended=args.extended)
        except (ValueError, RuntimeError) as e:
            upcoming.append({"show": show, "error": str(e)})
            continue

        for ep in episodes:
            air_dt = _parse_simkl_datetime(ep.get("date"))
            if not air_dt:
                continue
            air_utc = air_dt.astimezone(timezone.utc)
            if include_past_since <= air_utc <= window_end:
                upcoming.append(
                    {
                        "show": show,
                        "status": item.get("status"),
                        "last_watched": item.get("last_watched"),
                        "last_watched_at": item.get("last_watched_at"),
                        "watched_episodes_count": item.get("watched_episodes_count"),
                        "total_episodes_count": item.get("total_episodes_count"),
                        "not_aired_episodes_count": item.get("not_aired_episodes_count"),
                        "episode": ep,
                        "air_date": ep.get("date"),
                        "air_date_utc": air_utc.isoformat(),
                        "hours_until": round((air_utc - now).total_seconds() / 3600, 2),
                    }
                )

    upcoming.sort(key=lambda row: row.get("air_date_utc", ""))
    result = {
        "generated_at": now.isoformat(),
        "window_hours": args.hours,
        "past_hours": args.past_hours,
        "status": args.status,
        "items": upcoming,
        "limitations": [
            "SIMKL episode dates may be release dates or midnight timestamps, not exact local broadcast times for every network.",
            "This command enriches the watching list with /tv/episodes/{simkl_id}; it does not modify SIMKL.",
        ],
    }
    print(json.dumps(result, indent=2))

def cmd_providers(args: argparse.Namespace) -> None:
    try:
        cfg = load_config(require_token=True)
    except ValueError as e:
        print(f"Config error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        tmdb_cfg = load_tmdb_config()
    except ValueError as e:
        print(f"Config error: {e}", file=sys.stderr)
        sys.exit(1)

    client = SimklClient(cfg)
    tmdb = TmdbClient(tmdb_cfg)

    try:
        watchlist = client.all_items(media_type="movies", status=args.status)
    except (ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    rows: list[dict] = []
    for item in watchlist.get("movies", []):
        movie = item.get("movie", {})
        title = movie.get("title", "Unknown")
        tmdb_id = movie.get("ids", {}).get("tmdb")

        if not tmdb_id:
            rows.append({"title": title, "tmdb_id": None, "error": "No TMDB id on this SIMKL entry"})
            continue

        try:
            response = tmdb.watch_providers(tmdb_id)
        except (ValueError, RuntimeError) as e:
            rows.append({"title": title, "tmdb_id": tmdb_id, "error": str(e)})
            continue

        rows.append(
            {
                "title": title,
                "tmdb_id": tmdb_id,
                "providers": providers_for_region(response, args.region),
            }
        )

    if args.format == "json":
        print(json.dumps({"status": args.status, "region": args.region, "items": rows}, indent=2))
        return

    for row in rows:
        if row.get("error"):
            print(f"{row['title']}: {row['error']}")
            continue
        providers = row["providers"]
        if not providers:
            print(f"{row['title']}: no watch providers found for {args.region}")
            continue
        summary = " | ".join(f"{category}={', '.join(names)}" for category, names in providers.items())
        print(f"{row['title']}: {summary}")


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


    p_upcoming = sub.add_parser(
        "upcoming",
        help="Find currently-watching shows with episodes airing soon",
    )
    p_upcoming.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Look ahead this many hours from now (default: 24)",
    )
    p_upcoming.add_argument(
        "--past-hours",
        type=int,
        default=6,
        help="Also include episodes released in the last N hours (default: 6)",
    )
    p_upcoming.add_argument(
        "--status",
        choices=sorted(VALID_STATUSES),
        default="watching",
        help="Watchlist status to inspect (default: watching)",
    )
    p_upcoming.add_argument(
        "--extended",
        default="full",
        help="Extended info level (default: full)",
    )
    p_upcoming.add_argument(
        "--all",
        action="store_true",
        help="Check every show in the status list, not only shows with not-yet-aired episodes",
    )

    p_providers = sub.add_parser(
        "providers",
        help="Show TMDB watch-provider availability for movies on your SIMKL list",
    )
    p_providers.add_argument(
        "--status",
        choices=sorted(VALID_STATUSES),
        default="plantowatch",
        help="Watchlist status to inspect (default: plantowatch)",
    )
    p_providers.add_argument(
        "--region",
        default="US",
        help="ISO 3166-1 region code for provider availability (default: US)",
    )
    p_providers.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
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
    "upcoming": cmd_upcoming,
    "providers": cmd_providers,
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
