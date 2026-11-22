import json
import shutil

import pytest

from sofabaton_config import load_config, write_config


def entity(entity_id, name, sort, **extra):
    return {
        "kind": "device_backup",
        "captured_at": "2026-11-22T08:00:00+00:00",
        "fetched_at": "2026-11-22T08:00:01+00:00",
        "complete": True,
        "device": {"device_id": entity_id, "name": name, "sort": sort, "power_state": 1},
        "commands": [{"command_id": 1, "name": "Power"}],
        **extra,
    }


def backup():
    # Listed by id, as the hub's backup lists them; display order (sort) differs.
    return {
        "kind": "hub_bundle",
        "captured_at": "2026-11-22T08:00:00+00:00",
        "complete": True,
        "hub": {"name": "X2 HUB", "version": "X2"},
        "_progress_total_steps": 42,
        "devices": [entity(1, "Receiver", 1), entity(2, "Projector", 3), entity(3, "Media Player", 2)],
        "activities": [entity(101, "Watch Movie/TV", 2), entity(102, "Play PS5", 1)],
    }


def test_round_trip_drops_volatile_fields_and_keeps_display_order(tmp_path):
    write_config(backup(), tmp_path)

    assert load_config(tmp_path) == {
        "kind": "hub_bundle",
        "complete": True,
        "hub": {"name": "X2 HUB", "version": "X2"},
        "devices": [
            {"kind": "device_backup", "complete": True,
             "device": {"device_id": 1, "name": "Receiver", "sort": 1},
             "commands": [{"command_id": 1, "name": "Power"}]},
            {"kind": "device_backup", "complete": True,
             "device": {"device_id": 3, "name": "Media Player", "sort": 2},
             "commands": [{"command_id": 1, "name": "Power"}]},
            {"kind": "device_backup", "complete": True,
             "device": {"device_id": 2, "name": "Projector", "sort": 3},
             "commands": [{"command_id": 1, "name": "Power"}]},
        ],
        "activities": [
            {"kind": "device_backup", "complete": True,
             "device": {"device_id": 102, "name": "Play PS5", "sort": 1},
             "commands": [{"command_id": 1, "name": "Power"}]},
            {"kind": "device_backup", "complete": True,
             "device": {"device_id": 101, "name": "Watch Movie/TV", "sort": 2},
             "commands": [{"command_id": 1, "name": "Power"}]},
        ],
    }


def test_one_file_per_entity_with_readable_names(tmp_path):
    write_config(backup(), tmp_path)

    assert sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*.json")) == [
        "activities/101-watch-movie-tv.json",
        "activities/102-play-ps5.json",
        "devices/001-receiver.json",
        "devices/002-projector.json",
        "devices/003-media-player.json",
        "hub.json",
    ]
    assert json.loads((tmp_path / "devices/001-receiver.json").read_text())["device"]["name"] == "Receiver"


def test_export_again_leaves_no_stale_files(tmp_path):
    write_config(backup(), tmp_path)
    changed = backup()
    changed["devices"][0]["device"]["name"] = "Denon AVR"  # renamed
    del changed["devices"][1]  # Projector removed

    write_config(changed, tmp_path)

    assert sorted(p.name for p in (tmp_path / "devices").iterdir()) == [
        "001-denon-avr.json",
        "003-media-player.json",
    ]
    assert [d["device"]["name"] for d in load_config(tmp_path)["devices"]] == ["Denon AVR", "Media Player"]


def test_load_refuses_a_missing_folder(tmp_path):
    # A missing folder must not read as "the hub has no devices": apply would delete them all.
    write_config(backup(), tmp_path)
    shutil.rmtree(tmp_path / "devices")

    with pytest.raises(SystemExit):
        load_config(tmp_path)
