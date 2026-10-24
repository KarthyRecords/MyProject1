"""
Kobra 2 Neo serial capability check  v02
========================================
Standalone script: connects over USB, tries every read command the printer
might support, and prints a report of what works on THIS firmware.
The report (with every raw reply) is also saved as a text file next to
this script.

Safe to run while idle or printing:
  - only query commands are sent (nothing is heated, moved or saved)
  - the auto-report tests switch a report on for a few seconds and then
    off again (M155 / M154 / M27 S); the echo test does the same with M111
  - the SD file list is skipped while a print is running

"""
import os
import re
import time
from datetime import datetime

import serial
from serial.tools import list_ports

VERSION = "v02"
PORT = None            # None = auto-detect, or e.g. "COM3"
BAUD = 115200
AUTO_WATCH_S = 4       # seconds to watch each auto-report test
ECHO_WATCH_S = 5       # seconds to watch SD echo (only if printing)

NUM = r"[-+]?\d+(?:\.\d+)?"

# (group, command, what it gives, regex that proves real data came back)
CHECKS = [
    ("Live state", "M105", "Hotend/bed temperature + target",
     rf"T:{NUM}\s*/\s*{NUM}"),
    ("Live state", "M105", "Heater power (@: / B@:)", rf"@:{NUM}"),
    ("Live state", "M114", "X/Y/Z/E planned position",
     rf"X:{NUM}\s*Y:{NUM}\s*Z:{NUM}"),
    ("Live state", "M114", "Stepper counts (actual motor position)",
     r"Count\s+X:\s*-?\d+"),
    ("Live state", "M27", "SD print progress (bytes)",
     r"SD printing byte|Not SD printing"),
    ("Live state", "M27 C", "File being printed", r"Current file:"),
    ("Live state", "M31", "Elapsed print time", r"Print time:"),
    ("Live state", "M220", "Speed override %", r"FR:\s*\d+%"),
    ("Live state", "M221", "Flow override %", r"Flow:?\s*\d+%"),
    ("Live state", "M119", "Endstops / filament sensor",
     r"(?i)(x_min|x_max|z_min|filament)\s*:"),
    ("Live state", "M412", "Filament runout detection on/off",
     r"(?i)runout|filament"),
    ("Live state", "M211", "Software endstops on/off",
     r"(?i)soft\s*endstops|M211\s+S\d"),
    ("Setup", "M115", "Firmware info + capability list", r"FIRMWARE_NAME"),
    ("Setup", "M503", "All saved settings", r"M92|M203|M201"),
    ("Setup", "M301", "Hotend PID", r"(?i)\bp:?\s*" + NUM),
    ("Setup", "M304", "Bed PID", r"(?i)\bp:?\s*" + NUM),
    ("Setup", "M851", "Probe offset", rf"(?i)Z\s*:?\s*{NUM}"),
    ("Setup", "M900", "Linear advance K", rf"(?i)K\s*[:=]?\s*{NUM}"),
    ("Setup", "M420 V", "Bed levelling mesh",
     r"(?m)^\s*(?:echo:)?\s*\d+\s+[-+]?\d+\.\d+"),
    ("Setup", "M290", "Babystep / Z offset", rf"(?i)offset.*{NUM}"),
    ("Setup", "M20 L", "SD card file list", r"Begin file list"),
    ("Setup", "M78", "Lifetime print statistics", r"(?i)prints:|print time"),
    ("Setup", "M122", "Stepper driver status (TMC)",
     r"(?i)driver|tmc|stealth"),
    ("Setup", "M906", "Motor currents (TMC)", r"(?i)\bX\d*\s+driver|current"),
    ("Setup", "M123", "Fan tachometer speed", r"(?i)fan|rpm"),
]

AUTO_TESTS = [
    # (command on, command off, what, regex for an unsolicited line)
    ("M155 S1", "M155 S0", "Temperatures pushed automatically",
     rf"T:{NUM}\s*/\s*{NUM}"),
    ("M154 S1", "M154 S0", "Position pushed automatically",
     rf"X:{NUM}\s*Y:{NUM}"),
    ("M27 S1", "M27 S0", "SD progress pushed automatically",
     r"SD printing byte|Not SD printing"),
]

try:
    OUT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    OUT_DIR = os.getcwd()


# ---------------------------------------------------------------------------
def find_port():
    ports = list(list_ports.comports())
    for p in ports:
        if "CH340" in p.description or "USB-SERIAL" in p.description.upper():
            return p.device, ports
    return None, ports


class Printer:
    def __init__(self, port):
        self.s = serial.Serial()
        self.s.port, self.s.baudrate, self.s.timeout = port, BAUD, 0.2
        self.s.dtr = False                 # avoid resetting the printer
        self.s.open()

    def readline(self):
        raw = self.s.readline()
        return raw.decode(errors="ignore").strip() if raw else None

    def listen(self, seconds):
        lines, end = [], time.time() + seconds
        while time.time() < end:
            line = self.readline()
            if line:
                lines.append(line)
        return lines

    def send(self, cmd, timeout=4.0):
        """Return (reply lines, got_ok)."""
        self.s.write((cmd + "\n").encode())
        lines, end = [], time.time() + timeout
        while time.time() < end:
            line = self.readline()
            if not line:
                continue
            end = time.time() + timeout
            if line.startswith("echo:busy"):
                continue
            lines.append(line)
            if line.startswith("ok"):
                return lines, True
        return lines, False

    def close(self):
        self.s.close()


def classify(lines, got_ok, pattern):
    text = "\n".join(lines)
    if re.search(r"(?i)unknown command", text):
        return "NOT SUPPORTED"
    if pattern and re.search(pattern, text):
        return "OK"
    if not got_ok:
        return "NO REPLY"
    return "NO DATA"


ICON = {"OK": "[ OK ]", "NOT SUPPORTED": "[ -- ]", "NO DATA": "[ ?? ]",
        "NO REPLY": "[ !! ]", "SKIPPED": "[skip]"}


# ---------------------------------------------------------------------------
def main():
    stamp = datetime.now()
    port = PORT
    if port is None:
        port, ports = find_port()
        if port is None:
            print("Printer not found. Ports seen:")
            for p in ports:
                print(f"  {p.device} - {p.description}")
            print("Set PORT = 'COMx' at the top of the script.")
            return

    print(f"Connecting to {port} ...")
    pr = Printer(port)
    results, raw = [], []
    try:
        boot = pr.listen(2.5)
        reset_on_connect = any(l.strip() == "start" or "Marlin" in l
                               for l in boot)

        # Is a print running? (decides what is safe to run)
        lines, ok = pr.send("M27")
        printing = bool(re.search(r"SD printing byte (\d+)/(\d+)", "\n".join(lines))
                        ) and not re.search(r"byte 0/0", "\n".join(lines))

        caps = {}
        for group, cmd, what, pattern in CHECKS:
            if cmd == "M20 L" and printing:
                results.append((group, cmd, what, "SKIPPED",
                                "skipped while printing"))
                continue
            print(f"  {cmd:7s} {what} ...", end="", flush=True)
            lines, ok = pr.send(cmd, timeout=6.0 if cmd in ("M20 L", "M503",
                                                             "M122") else 4.0)
            status = classify(lines, ok, pattern)
            print(f" {status}")
            note = ""
            if cmd == "M115":
                caps = dict(re.findall(r"Cap:(\w+):(\d)", "\n".join(lines)))
                m = re.search(r"FIRMWARE_NAME:(.+?)(?:\s+SOURCE_CODE_URL|$)",
                              "\n".join(lines), re.M)
                note = m.group(1).strip() if m else ""
            elif status == "OK":
                body = [re.sub(r"^(ok\s+|echo:)", "", l).strip() for l in lines
                        if l.strip() != "ok" and "Reporting" not in l]
                hit = [b for b in body if re.search(pattern, b)] or body
                note = hit[0] if hit else ""
                if cmd == "M119":
                    note = ", ".join(b for b in body if ":" in b)
                note = note if len(note) <= 64 else note[:61] + "..."
                if cmd == "M420 V":
                    rows = [l for l in lines if re.match(
                        r"^\s*(?:echo:)?\s*\d+\s+[-+]?\d+\.\d+", l)]
                    note = f"{len(rows)} mesh rows"
                if cmd == "M20 L":
                    n = sum(1 for l in lines if re.search(r"\.(gco|gcode)", l, re.I))
                    note = f"{n} G-code file(s)"
            results.append((group, cmd, what, status, note))
            raw.append((cmd, lines))

        # Auto-report tests
        for on, off, what, pattern in AUTO_TESTS:
            print(f"  {on:7s} {what} ...", end="", flush=True)
            lines, ok = pr.send(on)
            if re.search(r"(?i)unknown command", "\n".join(lines)):
                status, note = "NOT SUPPORTED", ""
            else:
                seen = [l for l in pr.listen(AUTO_WATCH_S) if re.search(pattern, l)]
                status = "OK" if len(seen) >= 2 else "NO DATA"
                note = f"{len(seen)} reports in {AUTO_WATCH_S} s"
            pr.send(off)
            pr.listen(0.5)
            print(f" {status}")
            results.append(("Auto-report", on, what, status, note))
            raw.append((on, lines))

        # Echo test (M111)
        print("  M111 S1 echo mode ...", end="", flush=True)
        pr.send("M111 S1")
        lines, _ = pr.send("M31")
        usb_echo = any(l.startswith("echo:M31") for l in lines)
        sd_note, sd_status = "", "SKIPPED"
        if printing:
            watched = pr.listen(ECHO_WATCH_S)
            sd_lines = [l for l in watched
                        if re.match(r"^echo:(?:N\d+\s+)?[GM]\d+", l)]
            sd_status = "OK" if sd_lines else "NO DATA"
            sd_note = f"{len(sd_lines)} SD lines in {ECHO_WATCH_S} s"
            if sd_lines:
                sd_note += f", e.g. {sd_lines[0][5:][:40]}"
        else:
            sd_note = "start a print and run again to test this"
        pr.send("M111 S0")
        pr.listen(0.5)
        print(" done")
        results.append(("Echo", "M111 S1", "Echo of commands sent over USB",
                        "OK" if usb_echo else "NO DATA", ""))
        results.append(("Echo", "M111 S1", "Echo of commands from SD (during print)",
                        sd_status, sd_note))
        raw.append(("M111 S1 + M31", lines))
    finally:
        try:
            pr.s.write(b"M111 S0\nM155 S0\n")    # make sure nothing is left on
            pr.s.flush()
        except Exception:                          # noqa: BLE001
            pass
        pr.close()

    # ---- Report ----------------------------------------------------------
    out = []
    out.append("=" * 78)
    out.append(f"Kobra 2 Neo serial capability report   ({VERSION})")
    out.append(f"{stamp:%Y-%m-%d %H:%M:%S}   port {port}   "
               f"{'PRINTING' if printing else 'idle'}")
    out.append(f"Board reset when the port opened: "
               f"{'YES - do not connect mid-print' if reset_on_connect else 'no'}")
    out.append("=" * 78)
    group = None
    for g, cmd, what, status, note in results:
        if g != group:
            out.append(f"\n{g}")
            out.append("-" * len(g))
            group = g
        line = f"{ICON[status]} {cmd:8s} {what:42s}"
        if note:
            line += f"  {note}"
        out.append(line.rstrip())

    counts = {}
    for r in results:
        counts[r[3]] = counts.get(r[3], 0) + 1
    out.append("\nSummary: " + ",  ".join(f"{k} {v}" for k, v in counts.items()))
    out.append("[ OK ] works   [ -- ] not in this firmware   "
               "[ ?? ] replied but no data   [ !! ] no reply   [skip] skipped")

    if caps:
        on = sorted(k for k, v in caps.items() if v == "1")
        off = sorted(k for k, v in caps.items() if v == "0")
        out.append("\nM115 capabilities ON : " + ", ".join(on))
        out.append("M115 capabilities OFF: " + ", ".join(off))

    report = "\n".join(out)
    print("\n" + report)

    path = os.path.join(OUT_DIR, f"capability_report_{stamp:%Y%m%d_%H%M%S}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report + "\n\n" + "=" * 78 + "\nRAW REPLIES\n" + "=" * 78 + "\n")
        for cmd, lines in raw:
            f.write(f"\n>>> {cmd}\n" + "\n".join(lines) + "\n")
    print(f"\nSaved: {path}")


if __name__ == "__main__":
    main()
