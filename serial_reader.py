import threading

import serial


class SerialReader:
    def __init__(self, port: str, baud_rate: int, data_queue):
        self.port = port
        self.baud_rate = baud_rate
        self.queue = data_queue
        self._serial = None
        self._thread = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        self._serial = serial.Serial(self.port, self.baud_rate, timeout=1)
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._serial and self._serial.is_open:
            try:
                self._serial.close()
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._thread = None
        self._serial = None

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                if not self._serial or not self._serial.is_open:
                    break
                raw = self._serial.readline()
                line = raw.decode("utf-8", errors="replace").strip()
                if line:
                    try:
                        self.queue.put(float(line))
                    except ValueError:
                        print(f"[serial] non-float line: {line!r}")
            except serial.SerialException as exc:
                print(f"[serial] connection lost: {exc}")
                break
            except Exception as exc:
                if not self._stop_event.is_set():
                    print(f"[serial] unexpected error: {exc}")
                break
