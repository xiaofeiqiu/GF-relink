# Development Guide

This guide is the working reference for future feature development in this repo.

It is intentionally specific to this project. The goal is to help future work stay safe, consistent, and easy to extend without re-learning the same architecture and shutdown rules each time.

## Project Purpose

This app is a Windows desktop macro tool for `Granblue Fantasy: Relink`.

Current capabilities:
- Tk desktop UI
- Config selection
- Start/stop macro execution
- Live log display limited to the last 60 seconds
- Packaging into a Windows `.exe`

## Current Architecture

### Entry point

- [main.py](/abs/path/d:/poc/main.py:1)

Responsibilities:
- Configure process-wide logging
- Create the Tk root window
- Start the UI app

Keep `main.py` thin. Do not move runtime logic or business rules back into this file.

### UI layer

- [app/ui.py](/abs/path/d:/poc/app/ui.py:12)

Responsibilities:
- Build the Tk widgets
- Handle button events
- Poll log updates
- Reflect controller state into the UI

UI rules:
- Keep widget code here
- Keep controller/runtime logic out of this file
- UI code should call the controller instead of directly managing macro threads

### Runtime controller

- [app/controller.py](/abs/path/d:/poc/app/controller.py:10)

Responsibilities:
- Own the app-wide `DirectInputSender`
- Find the target game window
- Create and stop the single active macro worker thread
- Pass a shared `stop_event` into the running config

Controller rules:
- There must only be one active macro run at a time
- `start()` should refuse to start a second run if one is already active
- `stop()` must set the stop event, release held input, and join the worker thread
- Future runtime features should be added here before they are exposed in the UI

### Log buffering

- [app/log_buffer.py](/abs/path/d:/poc/app/log_buffer.py:1)

Responsibilities:
- Move log records from background threads into the UI safely
- Keep only the last 60 seconds of log lines

Rules:
- Keep log transport thread-safe
- Do not update Tk widgets from background worker threads
- UI updates must stay on the Tk thread

### Resource path resolution

- [app/paths.py](/abs/path/d:/poc/app/paths.py:5)

Responsibilities:
- Resolve the app root for source runs and PyInstaller runs
- Build absolute paths to bundled templates

Rules:
- Do not hardcode raw `templates/...` paths in new code
- Always resolve template assets through `template_path(...)`

### Macro config definitions

- [config.py](/abs/path/d:/poc/config.py:1)

Responsibilities:
- Define macro behavior
- Define watcher threads and automation logic
- Register available configs in `configs`

Rules:
- All macro configs must accept `(sender, hwnd, stop_event)`
- Add new configs to the `configs` dict
- Keep reusable helper functions above config registration

### Low-level input, detection, and capture

- [gbf/sender.py](/abs/path/d:/poc/gbf/sender.py:1)
- [gbf/detection.py](/abs/path/d:/poc/gbf/detection.py:1)
- [gbf/capture.py](/abs/path/d:/poc/gbf/capture.py:1)
- [gbf/window.py](/abs/path/d:/poc/gbf/window.py:1)
- [gbf/runner.py](/abs/path/d:/poc/gbf/runner.py:1)

These modules are the lower-level building blocks. Keep them focused and reusable.

## The Most Important Invariant: Clean Stop

This project must not leak worker threads or held input state across repeated `Start` and `Stop` cycles.

When changing macro logic, preserve these rules:

1. Every long-running loop must check `stop_event`.
2. Every wait on a `threading.Event` must be stoppable.
3. Every held key path must be stoppable.
4. Every worker thread created by a config must be joined during shutdown.
5. `sender.release_all()` must remain part of shutdown paths.

Current implementation points:
- `stop_event` is created by the controller and passed into the active config
- `config.py` uses `wait_or_stop(...)` and `wait_until_event_set(...)`
- held input in `DirectInputSender.hold(...)` accepts `stop_event`
- `shilaimu(...)` joins all watcher threads in `finally`

If you add a new watcher, check:
- Can it block forever?
- Does it honor `stop_event`?
- Will it exit if the window loses focus?
- Is it joined before the config returns?

## Focus Behavior

The current behavior is intentional:
- Watchers pause when the target game window is not focused
- Held inputs are released on focus loss

This behavior is coordinated in [config.py](/abs/path/d:/poc/config.py:361) via `monitor_window_focus(...)`.

If you change focus behavior, review:
- input safety
- stop behavior while unfocused
- whether background input is actually supported by the input backend

Do not remove focus checks casually. The current sender uses global-style desktop input and unfocused input is risky.

## How To Add a New Config

1. Add any new templates under `templates/`.
2. Add resolved template constants in `config.py` using `template_path(...)`.
3. Implement helper functions for the config logic.
4. Make sure every loop is stoppable with `stop_event`.
5. Join every thread created by the config in `finally`.
6. Register the config in `configs`.

When possible:
- share existing watcher helpers
- keep config-specific code grouped together
- avoid duplicating near-identical watcher/thread factory code unless the behavior genuinely differs

## How To Add New UI Features

Before adding UI controls, decide where the change belongs:

- UI-only presentation change:
  keep it in `app/ui.py`

- stateful runtime behavior:
  add it in `app/controller.py` first, then expose it in the UI

- reusable logging behavior:
  place it in `app/log_buffer.py`

Examples:
- New button that changes runtime behavior:
  add controller API first

- New display-only status label:
  UI-only is fine

- New long-running operation:
  avoid doing it directly in the Tk thread

## Template and Detection Conventions

Use `template_path("name.ext")` for template resolution.

Template guidance:
- Keep template filenames stable
- Prefer descriptive names
- Reuse a single screenshot when checking multiple templates in the same loop when possible
- Avoid unnecessary repeated capture/detect calls if a screenshot can be shared

If a feature needs many related templates, define their constants near the top of `config.py`.

## Packaging and Executable Build

- [Makefile](/abs/path/d:/poc/Makefile:1)

Current targets:
- `make bootstrap-build`
- `make exe`
- `make clean`

Notes:
- `make exe` builds a Windows app with PyInstaller
- templates are bundled with `--add-data "templates;templates"`
- asset loading works in both source and bundled runs through `app/paths.py`

If packaging changes:
- keep bundled asset handling compatible with PyInstaller
- do not reintroduce source-only relative paths

## Validation Workflow

Before finishing code changes, use this minimum check:

```powershell
.\.venv\Scripts\python.exe -m py_compile main.py app\__init__.py app\controller.py app\log_buffer.py app\paths.py app\ui.py config.py gbf\runner.py gbf\sender.py gbf\detection.py
```

If the change touches packaging:
- review `Makefile`
- verify asset paths still resolve

If the change touches threading or lifecycle:
- inspect every new loop and every new thread
- confirm the shutdown path still joins all threads

## Feature Design Checklist

Before implementing a new feature, answer these questions:

1. Is this UI logic, controller logic, or config logic?
2. Does it need a new controller API?
3. Does it create a new thread or long-running loop?
4. How does it stop?
5. Does it require new templates or bundled assets?
6. Does it affect packaging?
7. Does it preserve the one-active-run model?

If a feature fails this checklist, redesign before coding.

## Refactoring Preferences

Preferred direction:
- small focused modules
- explicit ownership of runtime state
- no hidden global mutable state
- clear stop/shutdown paths

Avoid:
- putting business logic back into `main.py`
- mixing Tk widget code with macro lifecycle logic
- adding blocking work directly to button handlers
- duplicating shutdown logic in multiple places

## Known Constraints

- Windows-only runtime assumptions
- Direct input is global-style and focus-sensitive
- template matching performance depends on capture frequency and screenshot size
- the app currently supports one active macro session at a time

## Suggested Future Improvements

Good next-step improvements if needed:
- add a dedicated config module per macro if `config.py` grows much larger
- extract repeated watcher thread factory patterns into a smaller abstraction
- add a lightweight smoke-test script for controller start/stop behavior
- add a build note for icon/version metadata in PyInstaller
- add a status model object if the UI grows beyond a few controls

## When In Doubt

If you are unsure where to put a change:
- runtime and lifecycle: `app/controller.py`
- widgets and button behavior: `app/ui.py`
- log retention and UI-safe log transport: `app/log_buffer.py`
- asset location rules: `app/paths.py`
- game-specific automation logic: `config.py`

Preserve clean stop behavior first. Everything else is secondary.
