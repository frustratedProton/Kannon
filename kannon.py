#!/usr/bin/env python3

import os
import pwd
import curses

CLOCK_TICKS = os.sysconf("SC_CLK_TCK")

def init_color():
    """ "curses color pairs for utilization"""
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)  # low usage
    curses.init_pair(2, curses.COLOR_YELLOW, -1)  # medium usage
    curses.init_pair(3, curses.COLOR_RED, -1)  # high usage
    curses.init_pair(4, curses.COLOR_CYAN, -1)  # headers / separators

def display_text(stdscr, row, col, text, attr=0):
    """
    Write text to screen, truncating at boundaries
    """
    max_y, max_x = stdscr.getmaxyx()
    if row < 0 or row >= max_y or col >= max_x or col < 0:
        return

    available = max_x - col
    if available <= 0:
        return
    text = str(text)[:available]
    try:
        stdscr.addstr(row, col, text, attr)
    except curses.error:
        pass


def bar_color(percent):
    """Return the curses attribute for a usage percentage"""
    if percent > 80:
        return curses.color_pair(3) | curses.A_BOLD
    elif percent > 50:
        return curses.color_pair(2) | curses.A_BOLD
    return curses.color_pair(1) | curses.A_BOLD


def draw_bar(stdscr, row, col, percent, width=20):
    """Returns a colored bar string like '[|||||     ] 50.0%'"""
    percent = max(0.0, min(100.0, percent))
    fill = int(width * (percent / 100))
    empty = width - fill
    color = bar_color(percent=percent)

    display_text(stdscr, row, col, "[")
    display_text(stdscr, row, col + 1, "|" * fill, color)
    display_text(stdscr, row, col + 1 + fill, " " * empty)
    display_text(stdscr, row, col + 1 + width, f"] {percent:>5.1f}%")


def calculate_cpu_usage(curr, prev):  # -> float | Any:
    """Calculate CPU usage % from two (total, idle) snapshots
    Returns:
    """
    total_d = curr[0] - prev[0]
    idle_d = curr[1] - prev[1]
    if total_d <= 0:
        return 0.0
    return ((total_d - idle_d) / total_d) * 100


def get_cpu_stats():  # -> dict | None:
    """
    Reads /proc/stat.
    """

    stats = {}

    try:
        with open(f"/proc/stat") as f:
            lines = f.readlines()

            for line in lines:
                if not line.startswith("cpu"):
                    break

                fields = line.split()
                name = fields[0]
                values = [float(x) for x in fields[1:]]

                if len(values) >= 10:
                    values[0] -= values[8]  # user -= guest
                    values[1] -= values[9]  # nice -= guest_nice

                # Total CPU Time = user + nice + system + idle + iowait + irq + softirq + steal
                total_cpu_time = sum(values[:8])
                # idle + iowait
                idle_cpu_time = values[3] + values[4]

                stats[name] = (total_cpu_time, idle_cpu_time)
            return stats
    except (FileNotFoundError, PermissionError, ValueError):
        return {}


def get_process_info(pid):  # -> dict[str, Any] | None:
    """
    Reads process details from /proc.
    Returns dict {pid, name, state, ppid, user} or None on failure.

    Args:
        pid (str): process id
    """
    try:
        with open(f"/proc/{pid}/stat") as f:
            content = f.read()

        first_paran = content.find("(")
        last_paran = content.rfind(")")

        # instead of using /proc/:pid/comm, we can just
        # use /proc/:pid/stat to get it
        name = content[first_paran + 1 : last_paran]

        fields = content[last_paran + 2 :].split()
        state = fields[0]
        ticks = int(fields[11]) + int(fields[12])  # utime + stime

        uid = None
        rss = 0

        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("Uid:"):
                    uid = int(line.split()[1])
                elif line.startswith("VmRSS:"):
                    rss = int(line.split()[1])

        if uid is None:
            return None

        return {
            "pid": pid,
            "name": name,
            "state": state,
            "ticks": ticks,
            "cpu_time": ticks / CLOCK_TICKS,
            "uid": uid,
            "rss": rss,
        }

    except (PermissionError, FileNotFoundError, ValueError, IndexError):
        return None


def get_user(uid, cache):
    if uid in cache:
        return cache[uid]
    try:
        user = pwd.getpwuid(uid).pw_name
    except KeyError:
        user = str(uid)
    cache[uid] = user
    return user


def get_memory_info():
    """Returns (mem_total, mem_available, swap_total, swap_free) from /proc/meminfo"""
    total_memory = available_memory = swap_total = swap_free = 0
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemTotal:"):
                total_memory = int(line.split()[1])
            elif line.startswith("MemAvailable:"):
                available_memory = int(line.split()[1])
            elif line.startswith("SwapTotal:"):
                swap_total = int(line.split()[1])
            elif line.startswith("SwapFree:"):
                swap_free = int(line.split()[1])
    return total_memory, available_memory, swap_total, swap_free


def format_kb(kb):
    """Formats kB as human-readable string"""
    if kb < 1024:
        return f"{kb}K"
    elif kb < 1024 * 1024:
        return f"{kb / 1024:.1f}M"
    else:
        return f"{kb / (1024 * 1024):.1f}G"


def format_time(seconds):
    """Formats seconds as H:MM:SS or M:SS"""
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}:{minutes:02}:{secs:02}"
    return f"{minutes}:{secs:02}"


def get_uptime():
    """Returns formatted uptime string"""
    with open("/proc/uptime") as f:
        total_seconds = float(f.read().split()[0])

    days = int(total_seconds // 86400)
    hours = int((total_seconds % 86400) // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)  

    if days > 0:
        return f"{days} days, {hours}:{minutes:02}:{seconds:02}"
    return f"{hours}:{minutes:02}:{seconds:02}"


def get_loadavg():
    """Returns load average string (1, 5, 15 min)"""
    with open("/proc/loadavg") as f:
        fields = f.read().split()
    return f"{fields[0]} {fields[1]} {fields[2]}"


def main(stdscr):
    init_color()
    curses.curs_set(0)
    stdscr.timeout(1000)

    prev_cpu_stats = get_cpu_stats()
    prev_procs = {}
    user_cache = {}
    cpu_count = os.cpu_count() or 1

    sort_key = "cpu"

    scroll_offset = 0
    max_proc_rows = 0

    while True:
        stdscr.erase()
        max_y, max_x = stdscr.getmaxyx()
        display_list = []

        if max_y < 10 or max_x < 40:
            display_text(stdscr, 0, 0, "Terminal too small!", curses.A_BOLD)
        else:
            curr_cpu_stats = get_cpu_stats()
            row = 0

            cores = sorted(
                [k for k in curr_cpu_stats if k != "cpu"],
                key=lambda x: int(x.replace("cpu", "")),
            )

            if cores:
                label_width = len(f"CPU{cores[-1].replace('cpu', '')}")
            else:
                label_width = 3
            label_width = max(label_width, 3)

            bar_width = max(5, (max_x - 4 - 2 * (label_width + 11)) // 2)

            agg_curr = curr_cpu_stats.get("cpu", (0, 0))
            agg_prev = prev_cpu_stats.get("cpu", (0, 0))
            global_usage = calculate_cpu_usage(agg_curr, agg_prev)
            avg_bar_width = 2 * bar_width + label_width + 13

            display_text(stdscr, row, 2, f"{'AVG':<{label_width}}: ", curses.A_BOLD)
            draw_bar(stdscr, row, 2 + label_width + 2, global_usage, avg_bar_width)
            row += 1

            half = (len(cores) + 1) // 2
            col_width = label_width + 2 + bar_width + 9

            for i in range(half):
                if row >= max_y:
                    break

                left_name = cores[i]
                left_usage = calculate_cpu_usage(
                    curr_cpu_stats[left_name],
                    prev_cpu_stats.get(left_name, (0, 0)),
                )
                display_text(stdscr, row, 2, f"{left_name.upper():<{label_width}}: ")
                draw_bar(stdscr, row, 2 + label_width + 2, left_usage, bar_width)

                j = i + half
                if j < len(cores):
                    rc = 2 + col_width + 2
                    right_name = cores[j]
                    right_usage = calculate_cpu_usage(
                        curr_cpu_stats[right_name],
                        prev_cpu_stats.get(right_name, (0, 0)),
                    )
                    display_text(
                        stdscr, row, rc, f"{right_name.upper():<{label_width}}: "
                    )
                    draw_bar(stdscr, row, rc + label_width + 2, right_usage, bar_width)
                row += 1

            if row < max_y:
                header = f"Uptime: {get_uptime()}  Load: {get_loadavg()}"
                display_text(
                    stdscr,
                    row,
                    max(0, max_x - len(header) - 1),
                    header,
                    curses.color_pair(4),
                )
                row += 1

            mem_total, mem_available, swap_total, swap_free = get_memory_info()
            mem_used = mem_total - mem_available
            mem_percent = (mem_used / mem_total) * 100 if mem_total else 0
            swap_used = swap_total - swap_free
            swap_percent = (swap_used / swap_total) * 100 if swap_total else 0

            mem_used_str = format_kb(mem_used)
            mem_total_str = format_kb(mem_total)
            swap_used_str = format_kb(swap_used)
            swap_total_str = format_kb(swap_total)

            val_width = max(
                len(mem_used_str),
                len(mem_total_str),
                len(swap_used_str),
                len(swap_total_str),
            )

            if row < max_y:
                lbl = (
                    f"  Mem: {mem_used_str:>{val_width}}/{mem_total_str:>{val_width}} "
                )
                display_text(stdscr, row, 0, lbl)
                draw_bar(stdscr, row, len(lbl), mem_percent, 20)
                row += 1

            if row < max_y:
                lbl = f"  Swp: {swap_used_str:>{val_width}}/{swap_total_str:>{val_width}} "
                display_text(stdscr, row, 0, lbl)
                draw_bar(stdscr, row, len(lbl), swap_percent, 20)
                row += 1

            sep = "=" * (max_x - 1)
            name_width = max(4, max_x - 67)

            if row < max_y:
                display_text(stdscr, row, 0, sep, curses.color_pair(4))
                row += 1

            if row < max_y:
                pid_label = "▼PID" if sort_key == "pid" else "PID"
                cpu_label = "▼%CPU" if sort_key == "cpu" else "%CPU"
                mem_label = "▼%MEM" if sort_key == "mem" else "%MEM"
                time_label = "▼TIME" if sort_key == "time" else "TIME"

                hdr = (
                    f"{pid_label:>7} | {'USER':<12} | {cpu_label:>6} | "
                    f"{mem_label:>6} | {time_label:>8} | {'STATE':^5} | {'NAME':<{name_width}}"
                )

                display_text(
                    stdscr,
                    row,
                    0,
                    hdr,
                    curses.A_BOLD | curses.color_pair(4),
                )
                row += 1

            if row < max_y:
                display_text(stdscr, row, 0, sep, curses.color_pair(4))
                row += 1

            pids = [p for p in os.listdir("/proc") if p.isdigit()]
            curr_procs_state = {}

            sys_total_delta = max(1, agg_curr[0] - agg_prev[0])

            for pid in pids:
                proc = get_process_info(pid)
                if not proc:
                    continue

                pid_int = int(proc["pid"])
                prev_ticks = prev_procs.get(pid_int, None)

                if prev_ticks is not None:
                    proc_delta = proc["ticks"] - prev_ticks
                    proc["cpu_usage"] = (proc_delta / sys_total_delta) * 100 * cpu_count
                else:
                    proc["cpu_usage"] = 0.0

                curr_procs_state[pid_int] = proc["ticks"]
                display_list.append(proc)

            if sort_key == "cpu":
                display_list.sort(key=lambda x: x["cpu_usage"], reverse=True)
            elif sort_key == "mem":
                display_list.sort(key=lambda x: x["rss"], reverse=True)
            elif sort_key == "pid":
                display_list.sort(key=lambda x: int(x["pid"]))
            elif sort_key == "time":
                display_list.sort(key=lambda x: x["cpu_time"], reverse=True)

            scroll_offset = max(0, min(scroll_offset, max(0, len(display_list) - 1)))

            footer_rows = 2
            max_proc_rows = max(0, max_y - row - footer_rows)

            visible_list = display_list[scroll_offset: scroll_offset + max_proc_rows]
            for proc in visible_list:
                if row >= max_y - footer_rows:
                    break

                user = get_user(proc["uid"], user_cache)
                name = proc["name"]

                proc_mem = (proc["rss"] / mem_total) * 100 if mem_total else 0

                if len(user) > 12:
                    user = user[:11] + "~"
                if len(name) > name_width:
                    name = name[: name_width - 1] + "…"

                line = (
                    f"{proc['pid']:>7} | {user:<12} | {proc['cpu_usage']:>5.1f}% "
                    f"| {proc_mem:>5.1f}% | {format_time(proc['cpu_time']):>8} "
                    f"| {proc['state']:^5} | {name:<{name_width}}"
                )

                if proc["cpu_usage"] > 50:
                    attr = curses.color_pair(3) | curses.A_BOLD
                elif proc["cpu_usage"] > 10:
                    attr = curses.color_pair(2)
                else:
                    attr = curses.color_pair(1)

                display_text(stdscr, row, 0, line, attr)
                row += 1

            footer_row = max_y - 2
            if footer_row >= row and footer_row < max_y:
                display_text(stdscr, footer_row, 0, sep, curses.color_pair(4))
            if footer_row + 1 < max_y:
                sort_labels = {
                    "cpu": "CPU%",
                    "mem": "MEM%",
                    "pid": "PID",
                    "time": "TIME",
                }

                status = (
                    f" Tasks: {len(display_list)} | "
                    f"Sort: {sort_labels[sort_key]} (P=CPU M=Mem N=PID T=Time) | q=Quit"
                )

                display_text(stdscr, footer_row + 1, 0, status, curses.A_BOLD)

            prev_cpu_stats = curr_cpu_stats
            prev_procs = curr_procs_state

        stdscr.refresh()

        key = stdscr.getch()
        if key == ord("q"):
            break
        elif key in (ord("P"), ord("p")):
            sort_key = "cpu"
            scroll_offset = 0
        elif key in (ord("M"), ord("m")):
            sort_key = "mem"
            scroll_offset = 0
        elif key in (ord("N"), ord("n")):
            sort_key = "pid"
            scroll_offset = 0
        elif key in (ord("T"), ord("t")):
            sort_key = "time"
            scroll_offset = 0
        elif key == curses.KEY_UP:
            scroll_offset = max(0, scroll_offset - 1)
        elif key == curses.KEY_DOWN:
            scroll_offset = min(max(0, len(display_list) - 1), scroll_offset + 1)
        elif key == curses.KEY_PPAGE:
            scroll_offset = max(0, scroll_offset - max_proc_rows)
        elif key == curses.KEY_NPAGE:
            scroll_offset = min(len(display_list) - 1, scroll_offset + max_proc_rows)
        elif key == curses.KEY_HOME:
            scroll_offset = 0
        elif key == curses.KEY_END:
            scroll_offset = max(0, len(display_list) - max_proc_rows)
        elif key == curses.KEY_RESIZE:
            stdscr.clear()


if __name__ == "__main__":
    curses.wrapper(main)
