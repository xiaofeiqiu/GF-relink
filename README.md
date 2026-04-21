# GBF Macro UI

This app is a simple desktop tool for running the `Granblue Fantasy: Relink` macro.

It provides:
- a config dropdown
- a `Start` button
- a `Stop` button
- a live log view showing the last 1 minute of logs

## How To Run

### Option 1: Run the packaged app

After building, the app executable is here:

- [gbf-macro.exe](/abs/path/d:/poc/dist/gbf-macro/gbf-macro.exe)

If the `dist` folder does not exist yet, build it first:

```powershell
.\build.ps1 bootstrap-build
.\build.ps1 exe
```

### Option 2: Run from source

```powershell
.\.venv\Scripts\python.exe main.py
```

## How To Use

1. Start the game and make sure the target window title matches `Granblue Fantasy: Relink`.
2. Launch the app.
3. Choose a config from the dropdown.
4. Click `Start`.
5. Keep the game window focused while the macro is running.
6. Click `Stop` to stop all macro threads cleanly.

## Important Notes

- The macro is designed for the focused game window.
- If the game window loses focus, watchers pause automatically.
- Only one macro run can be active at a time.
- `Stop` is designed to terminate the running macro threads and release held input.

## Build Commands

```powershell
.\build.ps1 bootstrap-build
.\build.ps1 exe
.\build.ps1 clean
```

Build output:
- [dist/gbf-macro](/abs/path/d:/poc/dist/gbf-macro)

## Troubleshooting

### `No module named PyInstaller`

Run:

```powershell
.\build.ps1 bootstrap-build
```

Then build again:

```powershell
.\build.ps1 exe
```

### The app cannot find the game window

Make sure:
- the game is running
- the window title is `Granblue Fantasy: Relink`
- the game is not closed or minimized unexpectedly

### Inputs are not working as expected

Make sure the game window is focused while the macro is running.

### The log is empty

The UI only keeps the last 60 seconds of log messages, so older entries are removed automatically.
