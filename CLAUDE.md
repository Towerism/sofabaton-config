# sofabaton-config

`hub/` is the source of truth for the owner's Sofabaton X2 hub. Keep it equal to what the hub holds, so the repo can be read to reason about the setup and used to rebuild it.

## Before any hub command

1. Ask the owner to fully close the Sofabaton app on every phone and tablet. Done when they confirm. Why: the hub serves one controller at a time; with the app open, `hubconfig` stops with "hub not controllable".
2. Make sure no other session is talking to the hub. Done when you have checked for other running sessions that use the hub. Why: two controllers fight over the one connection.

## Change the hub from the repo

1. Edit the files under `hub/`. Done when `git diff` shows only the intended change.
2. Run `uv run hubconfig plan`. Done when every line it prints is a change you meant, and nothing else. Why: the plan comes from the same planner `apply` runs, so an unexpected line is an unexpected write.
3. Run `uv run hubconfig apply`. It writes the differences and then exports again. Done when it prints "Exported the hub to hub/" and a second `plan` prints "The hub matches the config."
4. Commit `hub/` with a message that says what changed on the hub. Done when the commit is pushed.

## Bring the repo up to date after an app change

1. Run `uv run hubconfig export`. Done when it prints "Exported the hub to hub/".
2. Commit the diff with a message that says what changed and that it came from the app. Done when the commit is pushed.

## Rebuild a hub from the repo

`uv run hubconfig restore --yes-erase-hub` erases the hub and recreates every device and activity from `hub/`. Device and activity ids change, and the command exports afterwards, so commit the new ids. Run it only when the owner asks for a rebuild. Why: it deletes everything on the hub first, and nothing can undo that.

## Gotchas

- **New `wifi_ip` commands:** build the payload with `NetworkCommand.http(host=..., port=..., method="GET", path=...)` (request text, `restore_data.library_type` 28) and take its bytes and type together. The app-made commands are URL records (`library_type` 33, built by `NetworkCommand.url`). Why: URL-record bytes stored with type 28 are accepted by the hub, which then reports each press as sent while the device never gets the request.
- **`power_state` is left out of the files on purpose.** `desired_state()` copies the live value in before planning. Why: it changes whenever an activity runs, yet the planner compares it as part of each device record.
- **A press that reports `sent=True` proves nothing.** Prove a command by reading the target device's state after the hub presses it. For the Denon receiver, read it over telnet (port 23, commands end in `\r`). Ask the owner before pressing commands that change what the receiver is doing. Why: someone may be using it.
- **Denon speaker presets** (`SPPR 1`, `SPPR 2`) each keep their own Dirac Live slots (`PSDIRAC 1`–`3`). Name Dirac commands by slot number. Why: what a slot holds depends on the active speaker preset.

## Tests

`uv run pytest`. The planner tests read the committed `hub/`, so run them after every export. Why: they catch a library upgrade or a config edit that the planner would reject.
