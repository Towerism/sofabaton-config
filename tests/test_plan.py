"""The library's real planner, fed this repo's committed configuration."""

import copy
from pathlib import Path

from sofabaton.hub_sync import build_hub_sync_plan

from sofabaton_config import KINDS, desired_state, load_config

CONFIG = Path(__file__).resolve().parent.parent / "hub"


def live_hub(config):
    """What the hub reports: the same configuration plus its live power bytes."""
    live = copy.deepcopy(config)
    for kind in KINDS:
        for row in live[kind]:
            row["device"]["power_state"] = 1
    return live


def plan(baseline, config):
    return build_hub_sync_plan(baseline, desired_state(baseline, config), hub_version="X2")


def test_unchanged_config_plans_nothing():
    config = load_config(CONFIG)

    assert plan(live_hub(config), config).items == ()


def test_renamed_command_plans_exactly_one_rename():
    config = load_config(CONFIG)
    edited = copy.deepcopy(config)
    receiver = next(row for row in edited["devices"] if row["device"]["name"] == "Receiver")
    receiver["commands"][0]["name"] = "Renamed in the repo"

    items = plan(live_hub(config), edited).items

    assert [(item.kind, item.entity_id, [s.kind for s in item.steps]) for item in items] == [
        ("sync_device", receiver["device"]["device_id"], ["command_rename"]),
    ]
