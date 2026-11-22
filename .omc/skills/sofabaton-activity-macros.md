---
name: sofabaton-activity-macros
description: Add, change, reorder or remove activity macros and favorites on the Sofabaton hub through hub/ files, check the plan step by step, and prove each macro on the Denon receiver
triggers:
  - activity macro
  - sofabaton macro
  - hub macro
  - favorites order
  - quick access
  - dirac slot macro
  - speaker preset macro
---

# Change activity macros and favorites on the hub

Use this for macros and favorites inside `hub/activities/*.json`. Adding a new receiver command is a different path: follow CLAUDE.md "Add a network command", then come back here at step 2.

## Steps

1. **Preflight.** Follow CLAUDE.md "Before any hub command". Also check that `hub/` sits on the branch that holds the hub's latest changes. Done when the owner confirms the app is closed and `git log -1 -- hub/` is the commit the hub was last exported to.
   Why: a `hub/` taken from an older branch makes `plan` undo whatever the hub gained since.

2. **Export if the hub changed outside the files.** Run `uv run hubconfig export` after any library script, for example a newly added command. Done when it prints "Exported the hub to hub/".
   Why: the planner diffs the files against the hub, so a command missing from the files is planned as a delete.

3. **Edit `hub/` with a one-off script** kept in the job's tmp dir, not in the repo. The script loads with `load_config("hub")`, changes the bundle, then writes with `write_config(bundle, "hub")`. Done when a `jq` summary of each activity shows the intended macro names, step command ids, `favorite_slots` and `favorites_order`.
   - `sofabaton.edits` helpers (`add_favorite`, `remove_favorite`, ...) return a **copy** of the bundle. Re-fetch the activity row from the returned bundle after every helper call. Why: edits made to a row of the old bundle are silently lost. The first edit script here lost every activity except the first.
   - New macro: `button_id = max(edits._quick_access_ids(row) ≤ 197) + 1`.
   - Command step: `{device_id, command_id, button_code: 0, duration: 0, delay: 0}`.
   - Delay row: `{device_id: 0, command_id: 255, button_code: 281474976645120, duration: 0, delay: <seconds>}`.
   - Display order is `favorites_order`, a list of button ids that macros and favorites share.

4. **Read the plan with payloads.** Plain `plan` prints "Updating a macro…" for both new and rewritten macros. Print each step's kind and payload with `build_hub_sync_plan(snap.bundle, desired_state(snap.bundle, load_config("hub")), hub_version=...)`, as `sofabaton_config.run` does. Done when every `macro_write` (name, `new: true` or not), `macro_delete`, `favorite_add`/`favorite_delete` and `favorite_order` matches an intended change.

5. **Apply.** Run `uv run hubconfig apply`. Done when it prints "Exported the hub to hub/" and a second `plan` prints "The hub matches the config."
   - Thirty macro writes take a few minutes.
   - Output redirected to a file stays empty until the process exits. Judge progress with `ps` and with `ss -tnp` showing a connection to the hub, not by the log.

6. **Prove on the receiver.** Ask the owner first and say exactly what will change. Then:
   - Mute over telnet (`MUON`).
   - Press macros with `proxy.send(activity_id, m.command_id)`, taking `m` from `await proxy.macros(activity_id)`. The macro name is `m.label`.
   - Press favorites with `proxy.send(device_id, command_id)`.
   - After each press, poll `SPPR ?`, `PSDIRAC ?` and `MV?` for up to 20 s.
   - Finish by restoring the starting preset, slot and volume, then unmute.
   Done when every press reads back its expected values and the final state equals the starting one.

7. **Commit once** when all hub changes for the task are done (the repo squash-merges). Done when the commit is pushed.

## Gotchas

- **Preset switch race.** The Denon ignores a `PSDIRAC` sent within about 2 s of an `SPPR` switch; then Dirac reads `OFF` or stays on the old slot. On 2026-11-22, 2 s failed and 3 s worked. Any macro that sets a speaker preset and then a slot puts a delay row of at least 3 s between them; the listening macros use 4 s.
- **Test across a preset switch.** Each speaker preset remembers its last slot, so a macro whose slot command was ignored can still read back right by luck. Press a macro that switches presets and asks for a slot only the new preset has. For example, Movie -15dB (SPPR 1) then Movie -20dB (SPPR 2, slot 3).
- **Export noise that is expected.** Command steps written by the library export with `delay: 255`, and delay rows export with `device_id: 255`. These are the library's encodings, not defects (`sofabaton/macros.py` `_serialize_macro_key_entry`).
- **Empty slots.** A slot with no filter loaded is refused or turns Dirac off. Which curve sits in which preset and slot is read from the listening macros in `hub/activities/`. For example, "Movie -20dB" means SPPR 2, slot 3.
- **Test scripts.** Put `asyncio.run(main())` under `if __name__ == "__main__":`. Why: importing a helper from an unguarded test script presses every button again.
