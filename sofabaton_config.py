"""Keep a Sofabaton hub's configuration in files: export, plan, apply, restore."""

import argparse
import asyncio
import copy
import json
import os
import re
import shutil
from pathlib import Path

from sofabaton import AsyncXProxy
from sofabaton.hub_sync import build_hub_sync_plan

KINDS = ("devices", "activities")
# Change on every capture, so they would make every export a diff.
VOLATILE = {"captured_at", "fetched_at", "_progress_total_steps"}


def _display_order(rows):
    # The backup lists devices by id; the hub's own order is `sort`. Keeping
    # id order would make every plan "reorder" the hub's devices.
    return sorted(rows, key=lambda row: (row["device"]["sort"], row["device"]["device_id"]))


def _clean(row):
    row = {k: v for k, v in row.items() if k not in VOLATILE}
    row["device"] = {k: v for k, v in row["device"].items() if k != "power_state"}
    return row


def _write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_config(bundle, directory):
    """Write a hub backup as hub.json plus one file per device and activity."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    _write_json(directory / "hub.json", {k: v for k, v in bundle.items() if k not in VOLATILE and k not in KINDS})
    for kind in KINDS:
        folder = directory / kind
        shutil.rmtree(folder, ignore_errors=True)  # renamed or removed entities leave no stale file
        folder.mkdir()
        for row in bundle[kind]:
            entity = row["device"]
            slug = re.sub(r"[^a-z0-9]+", "-", entity["name"].lower()).strip("-")
            _write_json(folder / f"{entity['device_id']:03d}-{slug}.json", _clean(row))


def load_config(directory):
    """Join the files back into one hub backup document."""
    directory = Path(directory)
    bundle = json.loads((directory / "hub.json").read_text(encoding="utf-8"))
    for kind in KINDS:
        if not (directory / kind).is_dir():
            # Read as "no entries", a missing folder would make apply delete them all on the hub.
            raise SystemExit(f"{directory / kind} is missing; run export or restore the folder from git")
        rows = [json.loads(p.read_text(encoding="utf-8")) for p in (directory / kind).glob("*.json")]
        bundle[kind] = _display_order(rows)
    return bundle


def desired_state(baseline, config):
    """The config with each device's live power byte, which the files leave out.

    The planner treats power_state as part of a device's record, so without it
    every device would look edited; it is live state, not configuration.
    """
    live = {row["device"]["device_id"]: row["device"].get("power_state", 0) for kind in KINDS for row in baseline[kind]}
    desired = copy.deepcopy(config)
    for kind in KINDS:
        for row in desired[kind]:
            row["device"]["power_state"] = live.get(row["device"]["device_id"], 0)
    return desired


async def run(args, hub=AsyncXProxy, planner=build_hub_sync_plan):
    if args.command == "restore" and not args.yes_erase_hub:
        raise SystemExit("restore erases the hub before rebuilding it; pass --yes-erase-hub to go ahead")
    async with hub(hub_ip=args.hub) as proxy:
        if not await proxy.wait_until_controllable(timeout=30):
            raise SystemExit("hub not controllable: fully close the Sofabaton app on every phone and tablet")
        if not await proxy.wait_until_ready(timeout=60):
            raise SystemExit("the hub's catalogs did not become ready")

        if args.command == "restore":
            config = load_config(args.config)
            if not config["devices"]:
                raise SystemExit("the config has no devices; restore would leave the hub empty")
            result = await proxy.restore(config, replace=True)
            if not result.ok:
                raise SystemExit(f"restore stopped at {result.failed_at}; inspect the hub before retrying")
        elif args.command in ("plan", "apply"):
            snap = await proxy.refresh()
            desired = desired_state(snap.bundle, load_config(args.config))
            plan = planner(snap.bundle, desired, hub_version=(await proxy.status()).hub_version)
            for item in plan.items:
                print(item.label)
                for step in item.steps:
                    print(f"  {step.label}")
            if not plan.items:
                print("The hub matches the config.")
            for note in plan.notes:
                print(f"Note: {note}")
            if args.command == "plan" or not plan.items:
                return
            if any(item.kind.startswith("remove_") for item in plan.items) and not args.allow_delete:
                raise SystemExit("this plan deletes from the hub; check it, then run apply --allow-delete")
            result = await proxy.sync_hub(baseline=snap.bundle, desired=desired, snapshot_id=snap.snapshot_id)
            if result.status != "success":
                raise SystemExit(f"apply stopped at {result.failed_at}: {result.message}")

        # Export last, so the files hold what the hub stored (and any ids it assigned).
        bundle = await proxy.backup()
        if not bundle.get("complete"):
            raise SystemExit("the hub returned an incomplete backup; nothing was written, run export again")
        write_config(bundle, args.config)
        print(f"Exported the hub to {args.config}/")


def main():
    parser = argparse.ArgumentParser(prog="hubconfig", description=__doc__)
    parser.add_argument("command", choices=["export", "plan", "apply", "restore"])
    parser.add_argument("--hub", default=os.environ.get("SOFABATON_HUB"), required="SOFABATON_HUB" not in os.environ,
                        help="hub IP address (default: $SOFABATON_HUB)")
    parser.add_argument("--config", type=Path, default=Path("hub"), help="config directory (default: hub)")
    parser.add_argument("--yes-erase-hub", action="store_true", help="let restore erase the hub first")
    parser.add_argument("--allow-delete", action="store_true", help="let apply delete devices or activities")
    asyncio.run(run(parser.parse_args()))
