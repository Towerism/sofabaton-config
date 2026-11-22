# sofabaton-config

This repo holds the complete configuration of my Sofabaton X2 hub as files, and a small command, `hubconfig`, that runs on a computer on the same network as the hub. It copies the hub's configuration into the files, and copies changes made in the files back to the hub. To change the hub, you edit a file and run one command, and git shows the change as a diff. To use the tool with your own X2 hub, export that hub into the files first (step 4 below). I have only run it against my own hub.

I renamed one of the receiver's commands in `hub/devices/001-receiver.json`. `plan` then listed that rename as the only change. Its lines start with "Writing" because they list what `apply` would write. `apply` then made the change and read the hub back into `hub/`:

```console
$ uv run hubconfig plan
Writing device 'Receiver'…
  Renaming a command on device 1…
$ uv run hubconfig apply
Writing device 'Receiver'…
  Renaming a command on device 1…
Exported the hub to hub/
```

## Set it up

You need [uv](https://docs.astral.sh/uv/). It installs the right Python and the pinned `sofabaton-x` library.

1. Clone the repo and run `uv sync`.
2. Tell `hubconfig` where the hub is: `export SOFABATON_HUB=<your hub's IP address>` (mine is `192.168.0.59`), or pass `--hub` on each command.
3. Fully close the Sofabaton app on every phone and tablet. While the app is connected to the hub, `hubconfig` can't take control of it and stops with "hub not controllable".
4. If you are setting up your own hub, run `uv run hubconfig export` first. Export replaces the files in `hub/` with your hub's configuration. If you skip it, `apply` tries to make your hub match my files. It stops before deleting any of your devices or activities unless you pass `--allow-delete`, but it can still add mine and change yours.

## Run a command

| Command | What it does |
|---|---|
| `uv run hubconfig export` | Reads the whole hub into `hub/`. Run it after changing anything in the app, then commit. |
| `uv run hubconfig plan` | Lists what `apply` would change on the hub. Writes nothing. After an `apply`, it prints "The hub matches the config." |
| `uv run hubconfig apply` | Writes the changes in `hub/` to the hub, then exports, so the files match what the hub stored. If the plan deletes a device or activity, it stops and asks you to run `apply --allow-delete`. |
| `uv run hubconfig restore --yes-erase-hub` | Erases the hub and rebuilds every device and activity from `hub/`, then exports so the files get the new ids the hub assigns. If it stops partway, the hub may hold only part of its configuration; check the hub before you run it again. I have not run it against a real hub yet. |

`uv run pytest` runs the tests. They include a check that the library's planner accepts the committed files.

## What the files in `hub/` hold

Each device and each activity has its own JSON file, named after its id and name, such as `devices/001-receiver.json` or `activities/102-play-ps5.json`. A device file holds the device's commands in the form the hub sends them, such as an IR code or an HTTP request. It also holds the device's button assignments and macros. An activity file holds the activity's button assignments and macros, plus its favorites. `hub.json` holds the hub's name and model.

The files leave out values that change on their own, such as timestamps and whether a device is currently on, so a diff shows only changes someone made.

## How `hubconfig` talks to the hub

`hubconfig` talks to the hub through [sofabaton-x](https://github.com/m3tac0de/home-assistant-sofabaton-x1s/tree/main/sofabaton-x), an unofficial library for the hub's protocol, published on PyPI. The library's planner compares the files with the live hub and lists the entries that differ, and `apply` writes only those entries.

## How the receiver commands work

The **Receiver** device controls a Denon AVR-X3800H over the network. Each of its commands is an HTTP GET to the receiver's control page, for example `http://192.168.0.74:8080/goform/formiPhoneAppDirect.xml?MVUP` for volume up. Write a space inside a receiver command as `%20`, as in `PSDIRAC%202`. In testing, the receiver ignored a command that used `+` for the space.

Dirac Live is the receiver's room correction. The receiver stores up to three Dirac Live results in numbered slots. It also has two speaker presets, switched with the receiver commands `SPPR 1` and `SPPR 2`, and each preset has its own set of slots. On my receiver, choosing slot 1 under preset 2 selects a Dirac Live result, while choosing slot 1 under preset 1 turns Dirac Live off. The remote's buttons are therefore named by slot number ("Dirac Slot 1" to "Dirac Slot 3").

Adding a network command by editing a file and running `apply` has not been tested. The tested way is to add it with the library and then run `export`; [CLAUDE.md](CLAUDE.md) has the steps and the reason the stored format matters. The hub accepts a command stored in the wrong format and reports each press as sent, but the receiver doesn't respond to it.
