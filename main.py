import atexit
import json
import queue
import time
from pathlib import Path

import dearpygui.dearpygui as dpg
from serial.tools import list_ports

from data_manager import DataManager
from serial_reader import SerialReader

_UI_FONT = str(Path(__file__).parent / "DejaVuSansMono.ttf")

# ── Config ────────────────────────────────────────────────────────────────────

CONFIG_PATH = "./config.json"
_DEFAULTS = {
    "serial_port": "/dev/ttyUSB0",
    "baud_rate": 115200,
    "data_samples": 3000,
    "max_chart_points": 150,
    "smoothing_window": 3,
    "db_path": "./measures.db",
    "deadband": 0.01,
}


def _load_config() -> dict:
    try:
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        for k, v in _DEFAULTS.items():
            cfg.setdefault(k, v)
        return cfg
    except (FileNotFoundError, json.JSONDecodeError):
        _save_config(_DEFAULTS)
        return dict(_DEFAULTS)


def _save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


# ── Globals ───────────────────────────────────────────────────────────────────

config = _load_config()
db = DataManager(config["db_path"])
serial_q: queue.Queue = queue.Queue()
reader: SerialReader | None = None

state = {
    "recording": False,
    "streaming": True,
    "session_data": [],   # list of (ts: float, value: float)
    "chart_start": None,  # time.time() when x=0 was last reset
    "calibration": 0.0,
    "live_x": [],
    "live_y": [],
    "last_raw": 0.0,
    "pending_delete": None,
    "last_chart_value": 0.0,
    "view_pts": [],       # full data of currently displayed saved session
}

# ── Helpers ───────────────────────────────────────────────────────────────────


def _rolling_mean(values: list, window: int) -> list:
    if window <= 1 or len(values) == 0:
        return values
    result = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        result.append(sum(values[start : i + 1]) / (i - start + 1))
    return result


def _scan_ports() -> list[str]:
    return sorted(p.device for p in list_ports.comports())


def _refresh_ports() -> None:
    ports = _scan_ports()
    current = dpg.get_value("inp_port")
    if current and current not in ports:
        ports = [current] + ports
    dpg.configure_item("inp_port", items=ports)
    if ports and not current:
        dpg.set_value("inp_port", ports[0])


def _set_status(connected: bool) -> None:
    color = [0, 200, 0, 255] if connected else [200, 0, 0, 255]
    dpg.configure_item("dot", fill=color)


def _show_error(msg: str) -> None:
    dpg.set_value("err_msg", msg)
    dpg.show_item("dlg_error")


def _refresh_sessions() -> None:
    sessions = db.load_sessions()
    for child in (dpg.get_item_children("tbl_sessions", slot=1) or []):
        dpg.delete_item(child)
    for s in sessions:
        sid, sname, saved_at = s["id"], s["name"], s["saved_at"]
        with dpg.table_row(parent="tbl_sessions"):
            dpg.add_text(sname)
            dpg.add_text(saved_at)
            dpg.add_button(
                label="◉ Show",
                callback=lambda _s, _a, u: _show_session(*u),
                user_data=(sid, sname),
            )
            dpg.add_button(
                label="✕ Del",
                callback=lambda _s, _a, u: _confirm_delete(u),
                user_data=sid,
            )


def _show_session(session_id: int, name: str) -> None:
    pts = db.load_measurements(session_id)
    xs = [p["ts"] for p in pts]
    ys = [p["value"] for p in pts]
    state["view_pts"] = list(zip(xs, ys))
    dpg.set_value("saved_series", [xs, ys])
    dpg.set_value("saved_scatter", [[], []])
    dpg.configure_item("saved_scatter", show=False)
    dpg.set_value("chk_show_points", False)
    if xs:
        dpg.set_value("inp_view_from", xs[0])
        dpg.set_value("inp_view_to", xs[-1])
        dpg.fit_axis_data("saved_xax")
        dpg.fit_axis_data("saved_yax")
    dpg.configure_item("saved_plot", label=f"Session: {name}")


def _sync_scatter(xs: list, ys: list) -> None:
    if dpg.get_value("chk_show_points"):
        dpg.configure_item("saved_scatter", show=True)
        dpg.set_value("saved_scatter", [xs, ys])


def _apply_view_filter() -> None:
    pts = state["view_pts"]
    if not pts:
        return
    t_min = dpg.get_value("inp_view_from")
    t_max = dpg.get_value("inp_view_to")
    if t_min < t_max:
        filtered = [(x, y) for x, y in pts if t_min <= x <= t_max]
    else:
        filtered = pts
    xs = [p[0] for p in filtered]
    ys = [p[1] for p in filtered]
    dpg.set_value("saved_series", [xs, ys])
    _sync_scatter(xs, ys)
    if xs:
        dpg.fit_axis_data("saved_xax")
        dpg.fit_axis_data("saved_yax")


def _reset_view_filter() -> None:
    pts = state["view_pts"]
    if not pts:
        return
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    dpg.set_value("inp_view_from", xs[0])
    dpg.set_value("inp_view_to", xs[-1])
    dpg.set_value("saved_series", [xs, ys])
    _sync_scatter(xs, ys)
    dpg.fit_axis_data("saved_xax")
    dpg.fit_axis_data("saved_yax")


def cb_toggle_points(_, app_data) -> None:
    if app_data:
        xs, ys = dpg.get_value("saved_series")
        dpg.configure_item("saved_scatter", show=True)
        dpg.set_value("saved_scatter", [xs, ys])
    else:
        dpg.configure_item("saved_scatter", show=False)


def _confirm_delete(session_id: int) -> None:
    state["pending_delete"] = session_id
    dpg.show_item("dlg_delete")


# ── Callbacks ─────────────────────────────────────────────────────────────────


def cb_tare() -> None:
    state["calibration"] = state["last_raw"]


def cb_clear() -> None:
    dpg.show_item("dlg_clear")


def _do_clear() -> None:
    state["session_data"] = []
    state["live_x"] = []
    state["live_y"] = []
    state["chart_start"] = None
    state["last_chart_value"] = 0.0
    dpg.set_value("live_series", [[], []])
    dpg.hide_item("dlg_clear")


def cb_stop_resume() -> None:
    state["streaming"] = not state["streaming"]
    if state["streaming"]:
        dpg.set_item_label("btn_stop", "■ Stop")
        dpg.bind_item_theme("btn_stop", "theme_indigo")
    else:
        dpg.set_item_label("btn_stop", "▶ Resume")
        dpg.bind_item_theme("btn_stop", "theme_gray")


def cb_start() -> None:
    cb_tare()
    state["session_data"] = []
    state["live_x"] = []
    state["live_y"] = []
    state["chart_start"] = time.time()
    state["last_chart_value"] = 0.0
    state["recording"] = True
    dpg.set_value("live_series", [[], []])


def cb_save() -> None:
    if not state["session_data"]:
        return
    name = f"session-{int(time.time() * 1000)}"
    db.save_session(name, state["session_data"])
    _refresh_sessions()


def _do_delete() -> None:
    sid = state["pending_delete"]
    if sid is not None:
        db.delete_session(sid)
        state["pending_delete"] = None
        _refresh_sessions()
    dpg.hide_item("dlg_delete")


def cb_connect() -> None:
    global reader
    port = dpg.get_value("inp_port")
    try:
        baud = int(dpg.get_value("inp_baud"))
    except ValueError:
        _show_error("Invalid baud rate — must be an integer.")
        return
    config["serial_port"] = port
    config["baud_rate"] = baud
    _save_config(config)
    if reader:
        reader.stop()
        reader = None
    new_reader = SerialReader(port, baud, serial_q)
    try:
        new_reader.start()
        reader = new_reader
        _set_status(True)
    except Exception as exc:
        _set_status(False)
        _show_error(str(exc))


def cb_disconnect() -> None:
    global reader
    if reader:
        reader.stop()
        reader = None
    _set_status(False)


# ── Frame update ──────────────────────────────────────────────────────────────


def _drain_queue() -> None:
    while True:
        try:
            raw = serial_q.get_nowait()
        except queue.Empty:
            break

        state["last_raw"] = raw
        if not state["streaming"]:
            continue

        value = max(0.0, (raw - state["calibration"]) * 0.00981)
        dpg.set_value("txt_live_value", f"{value:.4f} N")

        deadband = 0.0 if value >= 1.0 else dpg.get_value("inp_deadband")
        if abs(value - state["last_chart_value"]) < deadband:
            continue
        state["last_chart_value"] = value

        if not state["recording"] or state["chart_start"] is None:
            continue

        ts = time.time() - state["chart_start"]
        state["live_x"].append(ts)
        state["live_y"].append(value)

        max_pts = config["max_chart_points"]
        x_win = state["live_x"][-max_pts:]
        y_win = _rolling_mean(state["live_y"][-max_pts:], config["smoothing_window"])
        dpg.set_value("live_series", [x_win, y_win])
        dpg.fit_axis_data("live_xax")
        dpg.fit_axis_data("live_yax")

        state["session_data"].append((ts, value))
        if len(state["session_data"]) >= config["data_samples"]:
            cb_save()
            state["recording"] = False


# ── UI construction ───────────────────────────────────────────────────────────


def _build_themes() -> None:
    with dpg.theme(tag="theme_indigo"):
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (75, 0, 130, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (105, 30, 170, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (55, 0, 100, 255))
    with dpg.theme(tag="theme_gray"):
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (120, 120, 120, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (150, 150, 150, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (90, 90, 90, 255))


def _build_ui() -> None:
    with dpg.window(
        tag="main_win",
        no_scrollbar=True,
        no_scroll_with_mouse=True,
    ):
        # ── Charts ────────────────────────────────────────────────────────────
        with dpg.group(horizontal=True):
            with dpg.plot(tag="live_plot", label="Live Data", width=620, height=400):
                dpg.add_plot_legend()
                dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)", tag="live_xax")
                dpg.add_plot_axis(dpg.mvYAxis, label="Thrust (N)", tag="live_yax")
                dpg.add_line_series([], [], label="Thrust (N)", tag="live_series", parent="live_yax")

            with dpg.plot(tag="saved_plot", label="Saved Session", width=-1, height=400):
                dpg.add_plot_legend()
                dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)", tag="saved_xax")
                dpg.add_plot_axis(dpg.mvYAxis, label="Thrust (N)", tag="saved_yax")
                dpg.add_line_series([], [], label="", tag="saved_series", parent="saved_yax")
                dpg.add_scatter_series([], [], label="Points", tag="saved_scatter", parent="saved_yax", show=False)

        # ── Saved-view time filter ────────────────────────────────────────────
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=630)
            dpg.add_text("View range (s)  From:")
            dpg.add_input_float(
                tag="inp_view_from",
                default_value=0.0,
                width=90,
                format="%.2f",
                step=0,
            )
            dpg.add_text(" To:")
            dpg.add_input_float(
                tag="inp_view_to",
                default_value=60.0,
                width=90,
                format="%.2f",
                step=0,
            )
            dpg.add_button(label="Apply", callback=_apply_view_filter)
            dpg.add_button(label="Reset", callback=_reset_view_filter)
            dpg.add_spacer(width=12)
            dpg.add_checkbox(
                label="Show points",
                tag="chk_show_points",
                default_value=False,
                callback=cb_toggle_points,
            )

        dpg.add_separator()

        # ── Live value + Dead band ─────────────────────────────────────────────
        with dpg.group(horizontal=True):
            dpg.add_text("Live thrust:")
            dpg.add_text("0.0000 N", tag="txt_live_value")
            dpg.add_spacer(width=40)
            dpg.add_text("Dead band (N):")
            dpg.add_input_float(
                tag="inp_deadband",
                default_value=0.01,
                min_value=0.0,
                step=0.001,
                format="%.4f",
                width=130,
            )

        dpg.add_separator()

        # ── Toolbar ───────────────────────────────────────────────────────────
        with dpg.group(horizontal=True):
            dpg.add_button(label="⊙ Tare", callback=cb_tare)
            dpg.add_button(label="✕ Clear", callback=cb_clear)
            dpg.add_button(label="■ Stop", tag="btn_stop", callback=cb_stop_resume)
            dpg.add_button(label="▶ Start", callback=cb_start)
            dpg.add_button(label="↓ Save", callback=cb_save)
            dpg.add_text("  status: ")
            with dpg.drawlist(width=20, height=20):
                dpg.draw_circle(
                    [10, 10], 8,
                    color=[0, 0, 0, 0],
                    fill=[200, 0, 0, 255],
                    tag="dot",
                )

        dpg.add_separator()

        # ── Serial settings ───────────────────────────────────────────────────
        with dpg.group(horizontal=True):
            dpg.add_text("Serial port:")
            _initial_ports = _scan_ports()
            _configured = config["serial_port"]
            if _configured and _configured not in _initial_ports:
                _initial_ports = [_configured] + _initial_ports
            dpg.add_combo(
                tag="inp_port",
                items=_initial_ports,
                default_value=_configured,
                width=200,
            )
            dpg.add_button(label="↻ Scan", callback=_refresh_ports)
            dpg.add_text("  Baud:")
            _BAUDS = ["300", "1200", "2400", "4800", "9600",
                      "19200", "38400", "57600", "115200", "230400"]
            dpg.add_combo(
                tag="inp_baud",
                items=_BAUDS,
                default_value=str(config["baud_rate"]),
                width=100,
            )
            dpg.add_button(label="⚡ Connect", callback=cb_connect)
            dpg.add_button(label="✂ Disconnect", callback=cb_disconnect)

        dpg.add_separator()

        # ── Sessions panel ────────────────────────────────────────────────────
        with dpg.group(horizontal=True):
            dpg.add_text("Saved sessions")
            dpg.add_button(label="↺ Refresh", callback=_refresh_sessions)

        with dpg.child_window(height=200, border=True):
            with dpg.table(
                tag="tbl_sessions",
                header_row=True,
                resizable=True,
                borders_innerH=True,
                borders_outerH=True,
                borders_innerV=True,
                borders_outerV=True,
                scrollY=True,
            ):
                dpg.add_table_column(
                    label="Name", width_stretch=True, init_width_or_weight=3
                )
                dpg.add_table_column(
                    label="Saved at", width_stretch=True, init_width_or_weight=3
                )
                dpg.add_table_column(
                    label="", width_fixed=True, init_width_or_weight=60
                )
                dpg.add_table_column(
                    label="", width_fixed=True, init_width_or_weight=60
                )

    # ── Modal dialogs (top-level) ─────────────────────────────────────────────
    with dpg.window(
        label="Confirm",
        tag="dlg_clear",
        modal=True,
        show=False,
        width=320,
        height=110,
        no_collapse=True,
        no_resize=True,
    ):
        dpg.add_text("Clear current session data?")
        dpg.add_separator()
        with dpg.group(horizontal=True):
            dpg.add_button(label="✓ Yes", width=130, callback=_do_clear)
            dpg.add_button(
                label="✗ No", width=130, callback=lambda: dpg.hide_item("dlg_clear")
            )

    with dpg.window(
        label="Confirm",
        tag="dlg_delete",
        modal=True,
        show=False,
        width=320,
        height=110,
        no_collapse=True,
        no_resize=True,
    ):
        dpg.add_text("Delete this session permanently?")
        dpg.add_separator()
        with dpg.group(horizontal=True):
            dpg.add_button(label="✓ Yes", width=130, callback=_do_delete)
            dpg.add_button(
                label="✗ No", width=130, callback=lambda: dpg.hide_item("dlg_delete")
            )

    with dpg.window(
        label="Error",
        tag="dlg_error",
        modal=True,
        show=False,
        width=440,
        height=150,
        no_collapse=True,
        no_resize=True,
    ):
        dpg.add_text("", tag="err_msg", wrap=420)
        dpg.add_separator()
        dpg.add_button(
            label="✓ OK", width=80, callback=lambda: dpg.hide_item("dlg_error")
        )


# ── Cleanup ───────────────────────────────────────────────────────────────────


def _cleanup() -> None:
    global reader
    if reader:
        reader.stop()
        reader = None


atexit.register(_cleanup)


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    dpg.create_context()

    with dpg.font_registry():
        with dpg.font(_UI_FONT, 16) as _app_font:
            pass
    dpg.bind_font(_app_font)

    _build_themes()
    _build_ui()

    dpg.bind_item_theme("btn_stop", "theme_indigo")

    dpg.create_viewport(title="Rocket Engine Testing Tool", width=1280, height=820)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("main_win", True)

    _refresh_sessions()

    # auto-connect on startup if a port is configured
    if config.get("serial_port"):
        cb_connect()

    while dpg.is_dearpygui_running():
        _drain_queue()
        dpg.render_dearpygui_frame()

    dpg.destroy_context()


if __name__ == "__main__":
    main()
