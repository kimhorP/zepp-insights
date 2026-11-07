"""CLI for the ETL layer.

Usage:
    python -m etl sync --from 2026-02-01 --to 2026-02-07
    python -m etl sync --type heart-rate
    python -m etl export --format csv --from 2026-02-01 --output data.csv
    python -m etl login
    python -m etl status
"""

import argparse
import json
import os
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from . import __version__
from .client import ZeppClient
from .exceptions import ZeppAPIError, ZeppAuthError
from .export import export_apple_health, export_csv
from .sync import ALL_DTYPES, count_days, iter_dates, sync_range, today

CONFIG_DIR = Path.home() / ".zepp-export"
CONFIG_FILE = CONFIG_DIR / "config"

DATA_TYPES = ALL_DTYPES + ["all"]


def resolve_credentials():
    """Resolve token and user ID: environment -> .env -> ~/.zepp-export/config."""
    load_dotenv()

    token = os.getenv("ZEPP_TOKEN") or os.getenv("HUAMI_APP_TOKEN")
    user_id = os.getenv("ZEPP_USER_ID") or os.getenv("HUAMI_USER_ID")
    base_url = os.getenv("ZEPP_BASE_URL")

    if not token or not user_id:
        if CONFIG_FILE.exists():
            for line in CONFIG_FILE.read_text().splitlines():
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip()
                if key == "ZEPP_TOKEN" and not token:
                    token = value
                elif key == "ZEPP_USER_ID" and not user_id:
                    user_id = value
                elif key == "ZEPP_BASE_URL" and not base_url:
                    base_url = value

    return token, user_id, base_url


def get_client() -> ZeppClient:
    token, user_id, base_url = resolve_credentials()
    if not token or not user_id:
        print("Error: No credentials found.")
        print()
        print("Set them in one of these locations (checked in order):")
        print("  1. Environment variables: ZEPP_TOKEN, ZEPP_USER_ID")
        print("  2. .env file in current directory")
        print("  3. ~/.zepp-export/config")
        print()
        print("Run 'python -m etl login' for setup instructions.")
        sys.exit(1)
    return ZeppClient(token=token, user_id=user_id, base_url=base_url)


def parse_date_range(args):
    from_date = getattr(args, "from_date", None)
    to_date = getattr(args, "to", None) or from_date
    if not from_date:
        from_date = today()
        to_date = from_date
    return from_date, to_date


# ------------------------------------------------------------------
# Commands
# ------------------------------------------------------------------

def cmd_sync(args):
    """Pull health data from Zepp into the SQLite database."""
    client = get_client()
    from_date, to_date = parse_date_range(args)
    dtype = args.type or "all"
    dtypes = None if dtype == "all" else [dtype]
    num_days = count_days(from_date, to_date)

    print(f"Syncing {dtype}: {from_date} to {to_date} ({num_days} days)")
    results = sync_range(client, from_date=from_date, to_date=to_date, dtypes=dtypes)

    failed = False
    for name, res in results.items():
        if res.get("ok"):
            print(f"  {name}: {res['rows']} rows")
        else:
            failed = True
            print(f"  {name}: FAILED - {res.get('error')}")

    if failed:
        sys.exit(1)


def cmd_export(args):
    """Export health data to a file format (pulls directly from the API)."""
    client = get_client()
    from_date, to_date = parse_date_range(args)
    fmt = args.format or "json"
    output = args.output
    data_type = args.type or "all"
    num_days = count_days(from_date, to_date)

    print(f"Exporting {data_type} as {fmt}: {from_date} to {to_date} ({num_days} days)")

    try:
        if fmt == "csv":
            if not output:
                output = f"zepp_{data_type}_{from_date}_to_{to_date}.csv"
            all_rows = []
            for i, date in enumerate(iter_dates(from_date, to_date)):
                if data_type in ("heart-rate", "all"):
                    for r in client.get_heart_rate(date):
                        all_rows.append({
                            "date": date, "type": "heart_rate", "time": r["time"],
                            "minute": r["minute"], "value": r["bpm"], "unit": "bpm",
                        })
                if data_type in ("steps", "all"):
                    steps = client.get_steps(date)
                    if steps:
                        all_rows.extend([
                            {"date": date, "type": "steps", "time": "", "minute": "",
                             "value": steps.get("total_steps"), "unit": "steps"},
                            {"date": date, "type": "distance", "time": "", "minute": "",
                             "value": steps.get("distance_meters"), "unit": "meters"},
                            {"date": date, "type": "calories", "time": "", "minute": "",
                             "value": steps.get("calories"), "unit": "kcal"},
                        ])
                if data_type in ("sleep", "all"):
                    sleep = client.get_sleep(date)
                    if sleep:
                        all_rows.extend([
                            {"date": date, "type": "sleep_score", "time": "", "minute": "",
                             "value": sleep.get("sleep_score"), "unit": "score"},
                            {"date": date, "type": "resting_hr", "time": "", "minute": "",
                             "value": sleep.get("resting_hr"), "unit": "bpm"},
                            {"date": date, "type": "deep_sleep", "time": "", "minute": "",
                             "value": sleep.get("deep_minutes"), "unit": "minutes"},
                            {"date": date, "type": "light_sleep", "time": "", "minute": "",
                             "value": sleep.get("light_minutes"), "unit": "minutes"},
                        ])
                print(f"  {date} ({i + 1}/{num_days})")
                if i < num_days - 1:
                    time.sleep(0.1)

            if data_type in ("stress", "all"):
                for s in client.get_stress(from_date, to_date):
                    for r in s.get("readings", []):
                        ts = r.get("time")
                        dt = datetime.fromtimestamp(ts / 1000) if isinstance(ts, (int, float)) else None
                        all_rows.append({
                            "date": dt.strftime("%Y-%m-%d") if dt else "",
                            "type": "stress",
                            "time": dt.strftime("%H:%M") if dt else "",
                            "minute": "",
                            "value": r.get("value"),
                            "unit": "stress_level",
                        })

            export_csv(all_rows, output)
            print(f"\nExported {len(all_rows)} rows to {output}")

        elif fmt == "apple-health":
            if not output:
                output = f"zepp_apple_health_{from_date}_to_{to_date}.xml"
            hr_data, steps_dict, sleep_dict = {}, {}, {}
            for i, date in enumerate(iter_dates(from_date, to_date)):
                if data_type in ("heart-rate", "all"):
                    hr_data[date] = client.get_heart_rate(date)
                if data_type in ("steps", "all"):
                    steps = client.get_steps(date)
                    if steps:
                        steps_dict[date] = steps
                if data_type in ("sleep", "all"):
                    sleep = client.get_sleep(date)
                    if sleep:
                        sleep_dict[date] = sleep
                print(f"  {date} ({i + 1}/{num_days})")
                if i < num_days - 1:
                    time.sleep(0.1)

            hr_count, steps_count, sleep_count = export_apple_health(
                heart_rate_data=hr_data or None,
                steps_data=steps_dict or None,
                sleep_data=sleep_dict or None,
                filepath=output,
            )
            print(f"\nExported to {output}:")
            print(f"  Heart rate records: {hr_count}")
            print(f"  Step count records: {steps_count}")
            print(f"  Sleep stage records: {sleep_count}")

        elif fmt == "json":
            if not output:
                output = f"zepp_{data_type}_{from_date}_to_{to_date}.json"
            all_data = {
                "date_range": {"from": from_date, "to": to_date},
                "extracted_at": datetime.now().isoformat(),
            }
            if data_type in ("heart-rate", "all"):
                all_data["heart_rate"] = {d: client.get_heart_rate(d)
                                          for d in iter_dates(from_date, to_date)}
            if data_type in ("sleep", "all"):
                all_data["sleep"] = {d: client.get_sleep(d)
                                     for d in iter_dates(from_date, to_date)}
            if data_type in ("steps", "all"):
                all_data["steps"] = {d: client.get_steps(d)
                                     for d in iter_dates(from_date, to_date)}
            if data_type in ("stress", "all"):
                all_data["stress"] = client.get_stress(from_date, to_date)
            if data_type in ("training-load", "all"):
                all_data["training_load"] = client.get_training_load(from_date, to_date)
            if data_type in ("sport-load", "all"):
                all_data["sport_load"] = client.get_sport_load(from_date, to_date)
            with open(output, "w", encoding="utf-8") as f:
                json.dump(all_data, f, indent=2, default=str)
            print(f"\nSaved to {output}")
        else:
            print(f"Unknown format: {fmt}")
            print("Supported formats: json, csv, apple-health")
            sys.exit(1)

    except ZeppAuthError as e:
        print(f"\nAuth error: {e}")
        sys.exit(1)
    except ZeppAPIError as e:
        print(f"\nAPI error: {e}")
        sys.exit(1)


def cmd_login(args):
    """Guide the user through getting and saving a token."""
    print("etl login")
    print("=" * 40)
    print()
    print("Step 1: Open the Zepp auth page in your browser")
    print("        https://user.huami.com/privacy/index.html")
    print()

    try:
        answer = input("Open in browser now? [Y/n] ").strip().lower()
        if answer != "n":
            webbrowser.open("https://user.huami.com/privacy/index.html")
            print("  Opened! Log in with your Zepp/Amazfit account.")
    except (EOFError, KeyboardInterrupt):
        print()

    print()
    print("Step 2: After logging in, open browser DevTools (F12)")
    print("        Go to Application -> Cookies -> user.huami.com")
    print("        Copy the 'apptoken' cookie value")
    print()

    try:
        token = input("Paste your apptoken: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.")
        return
    if not token:
        print("No token entered. Aborted.")
        return

    print()
    print("Step 3: Enter your Zepp user ID")
    print("        (visible in the Zepp app under Profile, or in API responses)")
    print()

    try:
        user_id = input("Your user ID: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.")
        return
    if not user_id:
        print("No user ID entered. Aborted.")
        return

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        f"# zepp-export credentials\n"
        f"# Saved by 'python -m etl login'\n"
        f"ZEPP_TOKEN={token}\n"
        f"ZEPP_USER_ID={user_id}\n"
    )

    print()
    print(f"Saved to {CONFIG_FILE}")
    print()
    print("Testing connection...")

    try:
        client = ZeppClient(token=token, user_id=user_id)
        t = today()
        steps = client.get_steps(t)
        if steps:
            print(f"  Connected! Today's steps: {steps.get('total_steps')}")
        else:
            print("  Connected! (no step data for today yet)")
        print()
        print("You're all set. Try:")
        print(f"  python -m etl sync --from {t}")
    except ZeppAuthError:
        print("  Token appears invalid or expired. Double-check and try again.")
    except ZeppAPIError as e:
        print(f"  Connection issue: {e}")


def cmd_status(args):
    """Show current credential status and account info."""
    print(f"zepp-insights etl v{__version__}")
    print()

    token, user_id, base_url = resolve_credentials()

    load_dotenv()
    env_token = os.getenv("ZEPP_TOKEN") or os.getenv("HUAMI_APP_TOKEN")
    config_token = None
    if CONFIG_FILE.exists():
        for line in CONFIG_FILE.read_text().splitlines():
            if line.startswith("ZEPP_TOKEN="):
                config_token = line.split("=", 1)[1].strip()

    if env_token:
        print("Token source: environment / .env")
    elif config_token:
        print(f"Token source: {CONFIG_FILE}")
    else:
        print("Token: NOT FOUND")
        print("Run 'python -m etl login' to set up.")
        return

    print(f"User ID: {user_id or 'NOT FOUND'}")
    print(f"API URL: {base_url or 'https://api-mifit-us2.zepp.com (default)'}")
    print()

    if token and user_id:
        print("Testing connection...")
        try:
            client = ZeppClient(token=token, user_id=user_id, base_url=base_url)
            t = today()
            steps = client.get_steps(t)
            if steps:
                print("  Status: Connected")
                print(f"  Today's steps: {steps.get('total_steps')}")
            else:
                print("  Status: Connected (no data for today yet)")
        except ZeppAuthError:
            print("  Status: TOKEN EXPIRED")
            print("  Run 'python -m etl login' to refresh.")
        except ZeppAPIError as e:
            print(f"  Status: Error - {e}")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="etl",
        description="zepp-insights ETL: pull Amazfit/Zepp health data into SQLite",
    )
    parser.add_argument("--version", action="version", version=f"etl {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    sync_parser = subparsers.add_parser("sync", help="Sync health data into the database")
    sync_parser.add_argument("--from", dest="from_date", help="Start date (YYYY-MM-DD)")
    sync_parser.add_argument("--to", help="End date (YYYY-MM-DD, default: today)")
    sync_parser.add_argument("--type", choices=DATA_TYPES, default="all",
                             help="Data type to sync (default: all)")

    export_parser = subparsers.add_parser("export", help="Export health data to a file format")
    export_parser.add_argument("--from", dest="from_date", help="Start date (YYYY-MM-DD)")
    export_parser.add_argument("--to", help="End date (YYYY-MM-DD)")
    export_parser.add_argument("--type", choices=DATA_TYPES, default="all",
                               help="Data type to export (default: all)")
    export_parser.add_argument("--format", "-f", choices=["json", "csv", "apple-health"],
                               default="json", help="Output format (default: json)")
    export_parser.add_argument("--output", "-o", help="Output file path")

    subparsers.add_parser("login", help="Set up Zepp API credentials")
    subparsers.add_parser("status", help="Show account status and connection info")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "sync":
        cmd_sync(args)
    elif args.command == "export":
        cmd_export(args)
    elif args.command == "login":
        cmd_login(args)
    elif args.command == "status":
        cmd_status(args)
    else:
        parser.print_help()
