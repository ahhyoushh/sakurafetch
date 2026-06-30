#!/usr/bin/env python3
import argparse
import curses
import math
import os
import platform
import random
import socket
import time

try:
    import psutil
except ImportError:
    psutil = None


UNICODE_FLUTTER = [("✿", "❀"), ("❀", "❁"), ("❁", "✾"), ("✾", "❋"), ("❋", "✿")]
ASCII_FLUTTER = [("*", "@"), ("@", "o"), ("o", "0"), ("0", "*")]

GROUND_RAMP_UNICODE = " ✾✿❀❁❋"
GROUND_RAMP_ASCII = " o0@*"
GROUND_MAX_LEVEL = min(len(GROUND_RAMP_UNICODE), len(GROUND_RAMP_ASCII)) - 1

LOGO = [
    "    /\\_/\\    ",
    "   ( o.o )   ",
    "    > ^ <    ",
    "   /     \\   ",
    "   ~~~~~~~   ",
]

THEMES = {
    "sakura": {"accent256": 211, "accent8": curses.COLOR_MAGENTA,
               "petals": [217, 218, 211, 213, 225, 224]},
    "matcha": {"accent256": 108, "accent8": curses.COLOR_GREEN,
               "petals": [151, 149, 108, 107, 150, 152]},
    "sumi":   {"accent256": 223, "accent8": curses.COLOR_YELLOW,
               "petals": [223, 222, 221, 220, 229, 224]},
    "rose":   {"accent256": 174, "accent8": curses.COLOR_RED,
               "petals": [217, 210, 204, 203, 174, 211]},
    "ocean":  {"accent256": 117, "accent8": curses.COLOR_BLUE,
               "petals": [117, 110, 109, 111, 153, 159]},
    "neon":   {"accent256": 213, "accent8": curses.COLOR_MAGENTA,
               "petals": [213, 207, 201, 129, 141, 147]},
}


def _bar(pct, width=10):
    filled = int(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


def _read_file(path):
    try:
        with open(path, "r") as f:
            return f.read()
    except OSError:
        return ""


def get_os_pretty_name():
    try:
        info = platform.freedesktop_os_release()
        if info.get("PRETTY_NAME"):
            return info["PRETTY_NAME"]
    except Exception:
        pass
    text = _read_file("/etc/os-release")
    for line in text.splitlines():
        if line.startswith("PRETTY_NAME="):
            return line.split("=", 1)[1].strip().strip('"')
    return f"{platform.system()} {platform.release()}".strip()


def get_kernel():
    return platform.release() or "Unknown"


def get_shell():
    sh = os.environ.get("SHELL", "")
    return os.path.basename(sh) if sh else "Unknown"


def get_terminal():
    return os.environ.get("TERM", "Unknown")


def get_cpu():
    text = _read_file("/proc/cpuinfo")
    for line in text.splitlines():
        if line.lower().startswith("model name"):
            return line.split(":", 1)[1].strip()
    proc = platform.processor()
    return proc if proc else "Unknown CPU"


def get_uptime():
    seconds = None
    if psutil is not None:
        try:
            seconds = time.time() - psutil.boot_time()
        except Exception:
            seconds = None
    if seconds is None:
        text = _read_file("/proc/uptime")
        if text:
            try:
                seconds = float(text.split()[0])
            except (ValueError, IndexError):
                seconds = None
    if seconds is None:
        return "n/a"
    h, rem = divmod(int(seconds), 3600)
    m, _ = divmod(rem, 60)
    d, h = divmod(h, 24)
    parts = []
    if d:
        parts.append(f"{d}d")
    parts.append(f"{h}h")
    parts.append(f"{m}m")
    return " ".join(parts)


def get_memory():
    if psutil is not None:
        try:
            vm = psutil.virtual_memory()
            used = vm.used / (1024**3)
            total = vm.total / (1024**3)
            pct = vm.percent
            bar = _bar(pct)
            return f"{bar}  {used:.1f}GiB / {total:.1f}GiB ({pct:.0f}%)"
        except Exception:
            pass
    text = _read_file("/proc/meminfo")
    vals = {}
    for line in text.splitlines():
        parts = line.split(":")
        if len(parts) == 2:
            try:
                vals[parts[0].strip()] = int(parts[1].strip().split()[0])
            except (ValueError, IndexError):
                continue
    if "MemTotal" in vals and "MemAvailable" in vals:
        total = vals["MemTotal"] / (1024**2)
        used = total - vals["MemAvailable"] / (1024**2)
        pct = used / total * 100
        bar = _bar(pct)
        return f"{bar}  {used:.1f}GiB / {total:.1f}GiB"
    return "n/a"


def get_battery():
    if psutil is not None:
        try:
            batt = psutil.sensors_battery()
            if batt is not None:
                status = "Charging" if batt.power_plugged else "Discharging"
                return f"{int(batt.percent)}% ({status})"
        except Exception:
            pass
    base = "/sys/class/power_supply"
    try:
        for entry in os.listdir(base):
            if entry.startswith("BAT"):
                cap = _read_file(f"{base}/{entry}/capacity").strip()
                status = _read_file(f"{base}/{entry}/status").strip()
                if cap:
                    return f"{cap}% ({status or 'Unknown'})"
    except OSError:
        pass
    return "No battery"


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        try:
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
        finally:
            s.close()
        if ip:
            return ip
    except Exception:
        pass
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "Unknown"


def gather_info():
    user = os.environ.get("USER") or os.environ.get("USERNAME") or "user"
    try:
        host = socket.gethostname().split(".")[0]
    except Exception:
        host = "localhost"
    return {
        "title": f"{user}@{host}",
        "os": get_os_pretty_name(),
        "kernel": get_kernel(),
        "uptime": get_uptime(),
        "shell": get_shell(),
        "terminal": get_terminal(),
        "cpu": get_cpu(),
        "memory": get_memory(),
        "battery": get_battery(),
        "local_ip": get_local_ip(),
    }


def floor_row(rows):
    return max(0, rows - 2)


class Petal:
    __slots__ = (
        "x",
        "y",
        "speed",
        "amp",
        "freq",
        "phase",
        "flutter",
        "flutter_speed",
        "color",
    )

    def __init__(self, cols, rows, ascii_mode, spawn_anywhere=False):
        self.respawn(cols, rows, ascii_mode, spawn_anywhere)

    def respawn(self, cols, rows, ascii_mode, spawn_anywhere=False):
        self.x = random.uniform(0, max(cols - 1, 1))
        self.y = (
            random.uniform(0, floor_row(rows))
            if spawn_anywhere
            else random.uniform(-rows, 0)
        )
        self.speed = random.uniform(3.0, 8.0)
        self.amp = random.uniform(0.6, 2.6)
        self.freq = random.uniform(0.5, 1.6)
        self.phase = random.uniform(0, math.tau)
        table = ASCII_FLUTTER if ascii_mode else UNICODE_FLUTTER
        self.flutter = random.choice(table)
        self.flutter_speed = random.uniform(1.0, 3.0)
        self.color = random.randint(0, 5)

    def glyph(self, t):
        idx = int(t * self.flutter_speed) % len(self.flutter)
        return self.flutter[idx]

    def update(self, dt, t, wind, cols, rows):
        self.y += self.speed * dt
        sway = math.sin(t * self.freq + self.phase) * self.amp
        self.x += (sway * dt) + wind * dt
        if self.x < 0:
            self.x += cols
        elif self.x >= cols:
            self.x -= cols


def safe_addstr(stdscr, y, x, text, attr=0):
    try:
        stdscr.addstr(y, x, text, attr)
    except curses.error:
        pass


def setup_colors(theme_name):
    curses.start_color()
    curses.use_default_colors()
    theme = THEMES.get(theme_name, THEMES["sakura"])
    pairs = {}

    if curses.COLORS >= 256:
        petal_codes = theme.get("petals", [217, 218, 211, 213, 225, 224])
        for i, code in enumerate(petal_codes):
            curses.init_pair(i + 1, code, -1)
            pairs[f"petal{i}"] = curses.color_pair(i + 1)
        curses.init_pair(10, theme["accent256"], -1)
        curses.init_pair(11, 246, -1)
        curses.init_pair(12, 223, -1)
        curses.init_pair(13, 217, -1)
        curses.init_pair(14, 255, -1)
    else:
        base = [curses.COLOR_MAGENTA, curses.COLOR_RED, curses.COLOR_WHITE]
        for i in range(6):
            code = base[i % len(base)]
            curses.init_pair(i + 1, code, -1)
            pairs[f"petal{i}"] = curses.color_pair(i + 1)
        curses.init_pair(10, theme["accent8"], -1)
        curses.init_pair(11, curses.COLOR_WHITE, -1)
        curses.init_pair(12, curses.COLOR_YELLOW, -1)
        curses.init_pair(13, curses.COLOR_MAGENTA, -1)
        curses.init_pair(14, curses.COLOR_WHITE, -1)

    pairs["accent"] = curses.color_pair(10)
    pairs["dim"] = curses.color_pair(11) | curses.A_DIM
    pairs["header"] = curses.color_pair(12) | curses.A_BOLD
    pairs["ground"] = curses.color_pair(13) | curses.A_DIM
    pairs["text"] = curses.color_pair(14)
    return pairs


def draw_ground(stdscr, ground, rows, cols, colors, ascii_mode):
    ramp = GROUND_RAMP_ASCII if ascii_mode else GROUND_RAMP_UNICODE
    y = floor_row(rows)
    for x in range(min(cols, len(ground))):
        level = ground[x]
        if level <= 0:
            continue
        idx = min(int(level), len(ramp) - 1)
        ch = ramp[idx]
        if ch != " ":
            safe_addstr(stdscr, y, x, ch, colors["ground"])


def draw_panel(stdscr, info, colors, rows, cols):
    width = 42
    rows_data = [
        ("OS", info["os"]),
        ("Kernel", info["kernel"]),
        ("Uptime", info["uptime"]),
        ("Shell", info["shell"]),
        ("Terminal", info["terminal"]),
        ("CPU", info["cpu"]),
        ("Memory", info["memory"]),
        ("Battery", info["battery"]),
        ("Local IP", info["local_ip"]),
    ]
    key_width = max(len(k) for k, _ in rows_data)
    inner_width = width - 4
    divider = " │ "
    val_width = inner_width - key_width - len(divider)
    height = len(LOGO) + 1 + 2 + len(rows_data) + 1 + 1 + 1 + 2

    if cols < width + 6 or rows < height + 2:
        return

    start_x = cols - width - 2
    start_y = max(1, (rows - height) // 2)
    if start_x < 0:
        return

    safe_addstr(
        stdscr, start_y, start_x, "╭" + "─" * (width - 2) + "╮", colors["accent"]
    )
    for i in range(1, height - 1):
        safe_addstr(stdscr, start_y + i, start_x, "│", colors["accent"])
        safe_addstr(stdscr, start_y + i, start_x + width - 1, "│", colors["accent"])
    safe_addstr(
        stdscr,
        start_y + height - 1,
        start_x,
        "╰" + "─" * (width - 2) + "╯",
        colors["accent"],
    )

    y = start_y + 1
    for logo_line in LOGO:
        safe_addstr(
            stdscr,
            y,
            start_x + (width - len(logo_line)) // 2,
            logo_line,
            colors["accent"],
        )
        y += 1

    y += 1
    safe_addstr(
        stdscr,
        y,
        start_x + (width - len(info["title"])) // 2,
        info["title"],
        colors["header"],
    )
    y += 1
    safe_addstr(stdscr, y, start_x + 2, "─" * inner_width, colors["accent"])
    y += 1

    for key, val in rows_data:
        val = val if len(val) <= val_width else val[: max(0, val_width - 1)] + "…"
        safe_addstr(stdscr, y, start_x + 2, f"{key:<{key_width}}", colors["header"])
        safe_addstr(stdscr, y, start_x + 2 + key_width, divider, colors["dim"])
        safe_addstr(
            stdscr, y, start_x + 2 + key_width + len(divider), val, colors["text"]
        )
        y += 1

    y += 1
    safe_addstr(stdscr, y, start_x + 2, "─" * inner_width, colors["accent"])
    y += 1
    x = start_x + 4
    for i in range(6):
        safe_addstr(stdscr, y, x, "████", curses.color_pair(i + 1))
        x += 6


def hint_text():
    return "[q] quit  [f] fetch  [a] ascii  [w] wind  [+/-] density  [space] pause  [h] hide"

def draw_hint(stdscr, rows, cols, colors, paused):
    text = hint_text()
    if paused:
        text = "PAUSED — " + text
    if len(text) > cols:
        text = text[: max(0, cols - 1)]
    safe_addstr(stdscr, rows - 1, max(0, (cols - len(text)) // 2), text, colors["dim"])


def run(stdscr, args):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(0)
    colors = setup_colors(args.theme)

    rows, cols = stdscr.getmaxyx()
    ascii_mode = args.ascii
    show_fetch = args.fetch
    show_overlay = True
    wind_on = not args.no_wind
    paused = False

    density = args.density
    num_petals = max(15, int(cols * density))
    petals = [
        Petal(cols, rows, ascii_mode, spawn_anywhere=True) for _ in range(num_petals)
    ]
    ground = [0.0] * cols

    info = gather_info() if show_fetch else None
    last_info_refresh = time.time()

    frame_time = 1.0 / max(1, args.fps)
    t = 0.0
    wind_phase = 0.0
    last = time.time()

    while True:
        now = time.time()
        dt = now - last
        last = now
        if dt > 0.1:
            dt = 0.1

        try:
            ch = stdscr.getch()
        except curses.error:
            ch = -1

        if ch in (ord("q"), ord("Q"), 27):
            break
        elif ch == ord("f"):
            show_fetch = not show_fetch
            if show_fetch and info is None:
                info = gather_info()
        elif ch == ord("a"):
            ascii_mode = not ascii_mode
            table = ASCII_FLUTTER if ascii_mode else UNICODE_FLUTTER
            for p in petals:
                p.flutter = random.choice(table)
        elif ch == ord("w"):
            wind_on = not wind_on
        elif ch == ord("h"):
            show_overlay = not show_overlay
        elif ch == ord(" "):
            paused = not paused
        elif ch in (ord("+"), ord("=")):
            for _ in range(max(1, cols // 20)):
                petals.append(Petal(cols, rows, ascii_mode, spawn_anywhere=True))
        elif ch == ord("-") and len(petals) > 10:
            for _ in range(min(len(petals) - 10, max(1, cols // 20))):
                petals.pop()
        elif ch == curses.KEY_RESIZE:
            rows, cols = stdscr.getmaxyx()
            ground = [0.0] * cols

        if show_fetch and now - last_info_refresh > 5:
            info = gather_info()
            last_info_refresh = now

        if not paused:
            t += dt
            wind_phase += dt * 0.15
            wind = math.sin(wind_phase) * (2.2 if wind_on else 0.0)
            wind += random.uniform(-0.05, 0.05) if wind_on else 0.0

            for p in petals:
                p.update(dt, t, wind, cols, rows)
                if p.y >= floor_row(rows):
                    cx = int(p.x) % cols
                    ground[cx] = min(GROUND_MAX_LEVEL, ground[cx] + 0.6)
                    p.respawn(cols, rows, ascii_mode)

            for i in range(len(ground)):
                if ground[i] > 0:
                    ground[i] = max(0.0, ground[i] - dt * 0.02)

        stdscr.erase()
        if show_overlay:
            draw_ground(stdscr, ground, rows, cols, colors, ascii_mode)

        for p in petals:
            yi, xi = int(p.y), int(p.x)
            if 0 <= yi < floor_row(rows) and 0 <= xi < cols:
                glyph = p.glyph(t)
                depth_attr = (
                    curses.A_BOLD
                    if p.speed > 6.5
                    else (curses.A_DIM if p.speed < 4.5 else 0)
                )
                safe_addstr(
                    stdscr, yi, xi, glyph, colors[f"petal{p.color}"] | depth_attr
                )

        if show_fetch and info is not None:
            draw_panel(stdscr, info, colors, rows, cols)

        if show_overlay:
            draw_hint(stdscr, rows, cols, colors, paused)

        stdscr.refresh()

        elapsed = time.time() - now
        remaining = frame_time - elapsed
        if remaining > 0:
            time.sleep(remaining)


def parse_args():
    p = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--fetch", action="store_true")
    p.add_argument("--ascii", action="store_true")
    p.add_argument("--theme", choices=sorted(THEMES.keys()), default="sakura")
    p.add_argument("--density", type=float, default=0.55)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--no-wind", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()
    try:
        curses.wrapper(run, args)
    except KeyboardInterrupt:
        pass
    except curses.error as e:
        print(f"sakura.py: {e}")


if __name__ == "__main__":
    main()
