# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

**Rocket Engine Testing Tool** — a single-process Python desktop app that reads real-time
thrust from an Arduino + HX711 load cell over serial, plots it live, records test runs,
and stores/reviews sessions in SQLite. It replaced an older Node.js + browser stack
(still present under `web/`, kept only for reference — do not extend it).

**Stack:** Python 3.10+, Dear PyGui (UI/charts), PySerial (serial I/O), `sqlite3` (stdlib).
No other runtime dependencies.

## Commands

```bash
pip install dearpygui pyserial   # install deps
python main.py                   # run the app (the only command needed to start)
python -m py_compile main.py     # quick syntax check (there is no test suite)
```

There are no unit tests, linters, or build steps configured. Validate changes by
compiling and, when possible, running the app.

## Architecture

```
main.py            Entry point: config load, Dear PyGui UI, frame loop, all callbacks & business rules
serial_reader.py   SerialReader — daemon thread that reads lines and pushes floats to a Queue
data_manager.py    DataManager — SQLite save/load/delete of sessions and measurements
config.json        Persisted settings (created from defaults if missing)
measures.db        SQLite store (created on first run)
DejaVuSansMono.ttf Bundled UI font
arduino/           HX711 sketch that streams one float per line over serial
web/               Legacy Node.js stack — reference only, not part of the app
```

**Data flow:** Arduino → serial line → `SerialReader._run` (thread) → `queue.Queue` →
`_drain_queue()` (called every frame on the main thread) → state → live chart + session buffer → SQLite.

**Threading rule:** serial reads MUST stay on the daemon thread and communicate only via the
`queue.Queue`. The UI/main thread never blocks on serial, and the reader thread never touches
Dear PyGui. Preserve this separation.

## Hardware contract

- Arduino + HX711, DOUT = pin 3, CLK = pin 2, RATE = pin 4 (HIGH = 80 SPS).
- HX711 scale factor `-105.1428` (calibrated for this specific load cell) → output is in **grams**.
- Arduino sends one `float` per line at **115200 baud** (`config.json` / sketch are the source of truth;
  the older docs mention 9600 — trust the code).

## Business rules (encoded as conditionals — keep them intact)

These are the explicit rules the project owner asked for. Each lives as a conditional in the code;
when editing, preserve the exact behavior unless told otherwise.

1. **Grams → Newtons + no negative thrust** — `main.py` `_drain_queue`:
   `value = max(0.0, (raw - calibration) * 0.00981)`.
   The tare-adjusted gram reading is multiplied by `0.00981` (g-force → N) and **clamped to ≥ 0**;
   negative readings are reported as `0.0`.

2. **Deadband only below 1.0 N** —
   `deadband = 0.0 if value >= 1.0 else inp_deadband`.
   At/above 1.0 N every sample passes through. Below 1.0 N, samples whose change from the last
   charted value is smaller than the deadband are dropped:
   `if abs(value - last_chart_value) < deadband: continue`. This suppresses idle noise without
   thinning the actual thrust curve.

3. **Record only while armed** —
   `if not recording or chart_start is None: continue`. Values are displayed live always, but only
   appended to the session/chart after `Start`.

4. **Auto-save at the sample cap** —
   `if len(session_data) >= data_samples: cb_save(); recording = False`. Hitting `data_samples`
   auto-saves the run and disarms recording.

5. **Paused stream still drains the queue** —
   when `streaming` is False, `_drain_queue` keeps reading the queue and updating `last_raw`
   (so the buffer never overflows and tare stays current) but skips charting and recording.

6. **Never save an empty session** —
   `cb_save`: `if not session_data: return`.

7. **Tare on Start** — `cb_start` calls `cb_tare()` first, so each run rebaselines the zero.
   `Tare` may also be called any time mid-session and never clears existing data.

8. **Live chart = sliding window + smoothing** — only the last `max_chart_points` samples are shown,
   passed through `_rolling_mean(..., smoothing_window)` before plotting.

9. **Saved-view time filter** — `_apply_view_filter`: `if t_min < t_max` filter points to
   `[t_min, t_max]`, otherwise show the full session.

10. **Config self-heals** — missing/corrupt `config.json` is recreated from `_DEFAULTS`; missing keys
    are backfilled via `setdefault`.

If you change any constant tied to these rules (the `0.00981` factor, the `1.0` N threshold,
`max(0.0, ...)` clamp, or the auto-save cap), call it out explicitly — these are physical/behavioral
decisions, not arbitrary numbers.

## Configuration (`config.json`)

| Key | Default | Purpose |
|-----|---------|---------|
| `serial_port` | `/dev/ttyUSB0` | Serial device (`COMx` on Windows) |
| `baud_rate` | `115200` | Serial baud rate |
| `data_samples` | `3000` | Samples before auto-save |
| `max_chart_points` | `150` | Points in the live sliding window |
| `smoothing_window` | `3` | Rolling-mean window for the live chart |
| `db_path` | `./measures.db` | SQLite database path |
| `deadband` | `0.01` | Default deadband (N), editable in the UI |

Note: `config.json` is listed in `.gitignore` ("Config with secrets") but is currently committed.
It is the source of truth for runtime settings — `_DEFAULTS` in `main.py` is only the fallback.

## Database schema (`measures.db`)

- `sessions(id, name, saved_at ISO-8601 UTC, samples)`
- `measurements(id, session_id → sessions.id ON DELETE CASCADE, ts REAL elapsed seconds, value REAL N)`

Foreign keys are enforced per-connection (`PRAGMA foreign_keys = ON`); deleting a session cascades
to its measurements.

## Error handling expectations

- Serial port not found → error dialog on connect, app keeps running without serial.
- Non-float serial line → skipped and logged, never crashes the reader.
- SQLite read error → log warning, skip, return empty list (don't crash the UI).
- Serial port is closed cleanly on exit via the `atexit`-registered `_cleanup`.

## Conventions

- Single-window, fixed layout; both charts (live + saved) are always visible.
- Internal helpers/private functions are prefixed `_`; UI callbacks are prefixed `cb_`.
- Dear PyGui items are referenced by stable string `tag`s; reuse the existing tag names.
- Mutable app state lives in the single `state` dict in `main.py`; `config` holds persisted settings.
- Match the existing style: type hints, section banner comments (`# ── … ──`), 4-space indent.
- Out of scope (per SPECS.md): networking/remote access, multiple serial connections, auth.
  CSV export is a possible future addition.
