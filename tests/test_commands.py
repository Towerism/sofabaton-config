"""Which hub writes each command makes, against a stand-in for the hub connection."""

import argparse
import asyncio
from types import SimpleNamespace

import pytest

from sofabaton_config import run, write_config

BUNDLE = {
    "kind": "hub_bundle",
    "hub": {"name": "X2 HUB", "version": "X2"},
    "devices": [{"device": {"device_id": 1, "name": "Receiver", "sort": 1}, "commands": []}],
    "activities": [],
}


class FakeHub:
    def __init__(self, plan_items=()):
        self.calls = []
        self.plan_items = plan_items

    def __call__(self, hub_ip):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def wait_until_controllable(self, timeout):
        return True

    async def wait_until_ready(self, timeout):
        return True

    async def status(self):
        return SimpleNamespace(hub_version="X2")

    async def refresh(self):
        return SimpleNamespace(bundle=BUNDLE, snapshot_id="snap-1")

    backup_result = {**BUNDLE, "complete": True}

    async def backup(self):
        self.calls.append("backup")
        return self.backup_result

    async def sync_hub(self, **kwargs):
        self.calls.append("sync_hub")
        return SimpleNamespace(status="success")

    async def restore(self, bundle, replace=False):
        self.calls.append(f"restore(replace={replace})")
        return SimpleNamespace(ok=True)


def run_command(command, config, hub, allow_delete=False):
    args = argparse.Namespace(command=command, hub="192.0.2.1", config=config, yes_erase_hub=False,
                              allow_delete=allow_delete)
    asyncio.run(run(args, hub=hub, planner=lambda baseline, desired, hub_version: SimpleNamespace(items=hub.plan_items, notes=())))


def test_restore_refuses_without_the_erase_flag(tmp_path):
    write_config(BUNDLE, tmp_path)
    hub = FakeHub()

    with pytest.raises(SystemExit):
        run_command("restore", tmp_path, hub)

    assert hub.calls == []


def test_restore_with_the_flag_erases_then_exports(tmp_path):
    write_config(BUNDLE, tmp_path)
    hub = FakeHub()

    args = argparse.Namespace(command="restore", hub="192.0.2.1", config=tmp_path, yes_erase_hub=True,
                              allow_delete=False)
    asyncio.run(run(args, hub=hub))

    assert hub.calls == ["restore(replace=True)", "backup"]


def test_apply_syncs_the_difference_then_exports(tmp_path):
    write_config(BUNDLE, tmp_path)
    hub = FakeHub(plan_items=(SimpleNamespace(kind="sync_device", label="Writing device 'Receiver'", steps=()),))

    run_command("apply", tmp_path, hub)

    assert hub.calls == ["sync_hub", "backup"]


def test_plan_writes_nothing(tmp_path):
    write_config(BUNDLE, tmp_path)
    hub = FakeHub(plan_items=(SimpleNamespace(kind="sync_device", label="Writing device 'Receiver'", steps=()),))

    run_command("plan", tmp_path, hub)

    assert hub.calls == []


DELETE = SimpleNamespace(kind="remove_device", label="Deleting device 'Projector'", steps=())


def test_apply_refuses_a_plan_that_deletes_without_the_flag(tmp_path):
    write_config(BUNDLE, tmp_path)
    hub = FakeHub(plan_items=(DELETE,))

    with pytest.raises(SystemExit):
        run_command("apply", tmp_path, hub)

    assert hub.calls == []


def test_apply_deletes_with_the_flag(tmp_path):
    write_config(BUNDLE, tmp_path)
    hub = FakeHub(plan_items=(DELETE,))

    run_command("apply", tmp_path, hub, allow_delete=True)

    assert hub.calls == ["sync_hub", "backup"]


def test_export_refuses_an_incomplete_backup(tmp_path):
    hub = FakeHub()
    hub.backup_result = {**BUNDLE, "complete": False}

    with pytest.raises(SystemExit):
        run_command("export", tmp_path / "hub", hub)

    assert not (tmp_path / "hub").exists()


def test_restore_refuses_a_config_with_no_devices(tmp_path):
    write_config({**BUNDLE, "devices": []}, tmp_path)
    hub = FakeHub()

    args = argparse.Namespace(command="restore", hub="192.0.2.1", config=tmp_path, yes_erase_hub=True,
                              allow_delete=False)
    with pytest.raises(SystemExit):
        asyncio.run(run(args, hub=hub))

    assert hub.calls == []
