# Rocket Engine Testing Tool — Python Desktop App Specs

## Overview

Desktop application to read real-time thrust measurements from an Arduino + HX711 load cell, display live charts, record test runs, and review saved sessions. Replaces the current Node.js + browser stack with a single Python process.

**Stack:** Python 3.10+, Dear PyGui, PySerial, SQLite3 (stdlib)

---

## Hardware context

- Arduino with HX711 load cell amplifier
- Pins: DOUT = 3, CLK = 2
- Scale factor: -105.1428 (calibrated for the specific load cell)
- Arduino sends one float per line over serial at 9600 baud
- Default sample interval: 2500 ms (configurable in Arduino sketch)

---

## Dependencies

```
dearpygui
pyserial
```

No other runtime dependencies. Standard library only beyond those two (`sqlite3` is included with Python).

---

## Project structure

```
rocket-measuring/
├── main.py               # entry point, UI
├── serial_reader.py      # serial reading thread
├── data_manager.py       # save/load sessions from SQLite
├── config.json           # persisted user settings
└── measures.db           # SQLite database with all sessions
```

---

## Configuration (`config.json`)

Persisted between runs. Editable from the Settings panel in the UI.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `serial_port` | string | `/dev/ttyUSB0` | Serial port path |
| `baud_rate` | int | `9600` | Serial baud rate |
| `data_samples` | int | `3000` | Samples before auto-save |
| `max_chart_points` | int | `100` | Max points shown in live chart |
| `db_path` | string | `./measures.db` | Path to the SQLite database file |

---

## Application layout

Single window, fixed layout with three panels:

```
┌─────────────────────────────────────────────────────────────────┐
│  Rocket Engine Testing Tool                                     │
├──────────────────────────────────┬──────────────────────────────┤
│                                  │                              │
│         Live Chart               │      Saved Session Chart     │
│         (real-time)              │      (shown on file select)  │
│                                  │                              │
├──────────────────────────────────┴──────────────────────────────┤
│  [Tare] [Clear] [Stop / Resume] [Start] [Save]  status: ●      │
├─────────────────────────────────────────────────────────────────┤
│  Serial port: [________] Baud: [____] [Connect] [Disconnect]   │
├─────────────────────────────────────────────────────────────────┤
│  Saved sessions                          [Refresh]              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ session-xxx  2024-04-01 12:30:00            [Show] [Del] │   │
│  │ session-yyy  2024-04-02 08:15:44            [Show] [Del] │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Functional requirements

### 1. Serial connection

- Connect to the configured serial port on app launch if `config.json` has a port set
- Show connection status indicator in the toolbar: green dot = connected, red = disconnected
- Reconnect button available at all times
- If connection fails, show an error dialog with the OS error message
- Serial reading runs in a `threading.Thread` (daemon=True), never on the main thread
- Each line received is stripped, parsed as `float`, and pushed to a thread-safe queue (`queue.Queue`)
- The UI polling loop drains the queue on every frame update

### 2. Live chart

- X axis: sample index (or elapsed time in seconds — see note below)
- Y axis: thrust in the unit returned by the Arduino (grams or Newtons depending on scale factor)
- Shows the last `max_chart_points` samples (sliding window)
- Chart updates on every new sample drained from the queue
- Y axis auto-scales to the data range

> **Note on X axis:** use elapsed seconds since the session started, not wall-clock time. This makes charts from different days comparable.

### 3. Tare

- Records the current reading as `calibration_value`
- All subsequent readings displayed and stored as `raw - calibration_value`
- Does not clear the current session data
- Can be called at any time, including mid-session

### 4. Start measurement

- Calls Tare first (sets new baseline)
- Clears current session buffer
- Sets `recording = True`
- When `len(session_data) >= data_samples`, auto-saves to the SQLite database and sets `recording = False`

### 5. Stop / Resume streaming

- Toggles whether incoming serial data is pushed to the live chart and session buffer
- Button label and color change to reflect state:
  - Active: label "Stop", indigo background
  - Paused: label "Resume", gray background
- Data is still read from serial while paused (buffer does not overflow); it is just not recorded or charted

### 6. Clear

- Prompts confirmation dialog before clearing
- Clears the session buffer and the live chart
- Does not disconnect serial or reset calibration

### 7. Save

- Saves current session buffer as a new row in the `sessions` table of `measures.db`
- Database schema:
  ```sql
  CREATE TABLE sessions (
      id        INTEGER PRIMARY KEY AUTOINCREMENT,
      name      TEXT NOT NULL,          -- e.g. "session-1711937841930"
      saved_at  TEXT NOT NULL,          -- ISO-8601 UTC timestamp
      samples   INTEGER NOT NULL        -- number of data points
  );

  CREATE TABLE measurements (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
      ts         REAL NOT NULL,         -- elapsed seconds since session start
      value      REAL NOT NULL          -- thrust reading (tare-adjusted)
  );
  ```
- Does not clear the buffer after saving (user can save multiple snapshots of the same run)
- Refreshes the saved sessions list automatically

### 8. Saved sessions panel

- Lists all sessions from the `sessions` table, ordered by `saved_at` descending
- Loads on app start (no manual refresh needed on first open)
- Each row shows the session name, saved timestamp, and two buttons: **Show** and **Delete**
- **Show:** queries the `measurements` table for that `session_id` and loads it into the Saved Session Chart
- **Delete:** prompts confirmation, then deletes the session row (cascade removes its measurements) and removes from list
- **Refresh** button available to re-query the database

### 9. Saved session chart

- Displayed side-by-side with the live chart (always visible, not a replacement)
- X axis: elapsed seconds computed from timestamps
- Y axis: measurement values parsed as float
- Chart title shows the session name of the loaded session
- On first load (no session selected), chart is empty with a placeholder label

---

## Non-functional requirements

- **No data loss:** serial reads happen in a dedicated thread with a queue; the UI never blocks the reader
- **Startup time:** app window should appear in under 2 seconds
- **Single file execution:** `python main.py` is the only command needed to start
- **Cross-platform:** code must run on Linux and Windows (port path format is the only OS-specific part, handled via `config.json`)
- **No internet required:** all assets are local, no CDN dependencies
- **Graceful shutdown:** serial port is closed cleanly on window close (`atexit` or Dear PyGui's `set_exit_callback`)

---

## Error handling

| Situation | Behavior |
|-----------|----------|
| Serial port not found | Error dialog on connect, app continues without serial |
| Malformed serial line (non-float) | Skip line, log to console, do not crash |
| `measures.db` missing | Create it and run schema migrations on startup |
| SQLite error on read | Skip session in list, log warning |
| `config.json` missing | Create with defaults on startup |

---

## Out of scope

- Network streaming or remote access
- Multiple simultaneous serial connections
- CSV export (can be added later)
- Authentication or user management
