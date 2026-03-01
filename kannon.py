#!/usr/bin/env python3

import os
import pwd
import curses


def init_colors():
    """Initialize curses color pairs"""
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)    # low usage
    curses.init_pair(2, curses.COLOR_YELLOW, -1)   # medium usage
    curses.init_pair(3, curses.COLOR_RED, -1)       # high usage
    curses.init_pair(4, curses.COLOR_CYAN, -1)      # headers / separators


def safe_addstr(stdscr, row, col, text, attr=0):
    """Write text to screen, silently truncating at boundaries"""
    max_y, max_x = stdscr.getmaxyx()
    if row < 0 or row >= max_y or col >= max_x:
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
    """Draw a colored usage bar: [|||||     ] 50.0%"""
    percent = max(0.0, min(100.0, percent))
    fill = int(width * (percent / 100))
    empty = width - fill
    color = bar_color(percent)

    safe_addstr(stdscr, row, col, "[")
    safe_addstr(stdscr, row, col + 1, "|" * fill, color)
    safe_addstr(stdscr, row, col + 1 + fill, " " * empty)
    safe_addstr(stdscr, row, col + 1 + width, f"] {percent:>5.1f}%")


def calculate_cpu_usage(curr, prev):
    """CPU usage % from two (total, idle) snapshots"""
    total_d = curr[0] - prev[0]
    idle_d = curr[1] - prev[1]
    if total_d <= 0:
        return 0.0
    return ((total_d - idle_d) / total_d) * 100


def get_cpu_stats():
    """Read /proc/stat and return {name: (total, idle)} dict"""
    stats = {}
    try:
        with open("/proc/stat") as f:
            for line in f:
                if not line.startswith("cpu"):
                    break
                fields = line.split()
                name = fields[0]
                values = [float(x) for x in fields[1:]]
                if len(values) >= 10:
                    values[0] -= values[8]
                    values[1] -= values[9]
                total_cpu_time = sum(values[:8])
                idle_cpu_time = values[3] + values[4]
                stats[name] = (total_cpu_time, idle_cpu_time)
    except (FileNotFoundError, PermissionError, ValueError):
        pass
    return stats


def get_process_info(pid):
    """Read process details from /proc/<pid>/{stat,status}"""
    try:
        with open(f"/proc/{pid}/stat") as f:
            content = f.read()

        first_paran = content.find("(")
        last_paran = content.rfind(")")
        name = content[first_paran + 1 : last_paran]

        fields = content[last_paran + 2 :].split()
        state = fields[0]
        ticks = int(fields[11]) + int(fields[12])

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
            "uid": uid,
            "rss": rss,
        }
    except (PermissionError, FileNotFoundError, ValueError, IndexError):
        return None


def get_user(uid, cache):
    """Resolve UID to username with caching"""
    if uid in cache:
        return cache[uid]
    try:
        user = pwd.getpwuid(uid).pw_name
    except KeyError:
        user = str(uid)
    cache[uid] = user
    return user


def get_memory_info():
    """Returns (mem_total, mem_available, swap_total, swap_free) in kB"""
    total = avail = swap_total = swap_free = 0
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemTotal:"):
                total = int(line.split()[1])
            elif line.startswith("MemAvailable:"):
                avail = int(line.split()[1])
            elif line.startswith("SwapTotal:"):
                swap_total = int(line.split()[1])
            elif line.startswith("SwapFree:"):
                swap_free = int(line.split()[1])
    return total, avail, swap_total, swap_free


def format_kb(kb):
    """Human-readable size from kB"""
    if kb < 1024:
        return f"{kb}K"
    elif kb < 1024 * 1024:
        return f"{kb / 1024:.1f}M"
    return f"{kb / (1024 * 1024):.1f}G"


def get_uptime():
    """Formatted uptime string"""
    with open("/proc/uptime") as f:
        secs = float(f.read().split()[0])
    days = int(secs // 86400)
    hours = int((secs % 86400) // 3600)
    mins = int((secs % 3600) // 60)
    s = int(secs % 60)
    if days > 0:
        return f"{days}d {hours:02}:{mins:02}:{s:02}"
    return f"{hours:02}:{mins:02}:{s:02}"


def get_loadavg():
    """Load average string (1, 5, 15 min)"""
    with open("/proc/loadavg") as f:
        fields = f.read().split()
    return f"{fields[0]} {fields[1]} {fields[2]}"


def main(stdscr):
    init_colors()
    curses.curs_set(0)
    stdscr.timeout(1000)

    prev_cpu_stats = get_cpu_stats()
    prev_procs = {}
    user_cache = {}
    cpu_count = os.cpu_count() or 1

    while True:
        stdscr.erase()
        max_y, max_x = stdscr.getmaxyx()

        if max_y < 10 or max_x < 40:
            safe_addstr(stdscr, 0, 0, "Terminal too small!", curses.A_BOLD)
            stdscr.refresh()
            key = stdscr.getch()
            if key == ord("q"):
                break
            continue

        curr_cpu_stats = get_cpu_stats()
        row = 0

        # ── CPU cores ───────────────────────────────────────────
        cores = sorted(
            [k for k in curr_cpu_stats if k != "cpu"],
            key=lambda x: int(x.replace("cpu", "")),
        )
        label_width = max(3, len(f"CPU{cores[-1].replace('cpu', '')}") if cores else 3)

        # aggregate bar (full width)
        agg_curr = curr_cpu_stats.get("cpu", (0, 0))
        agg_prev = prev_cpu_stats.get("cpu", (0, 0))
        global_usage = calculate_cpu_usage(agg_curr, agg_prev)
        avg_bar_width = max(5, max_x - label_width - 15)

        safe_addstr(stdscr, row, 2, f"{'AVG':<{label_width}}: ", curses.A_BOLD)
        draw_bar(stdscr, row, 2 + label_width + 2, global_usage, avg_bar_width)
        row += 1

        # two-column per-core bars
        half = (len(cores) + 1) // 2
        bar_width = max(5, (max_x - 4 - 2 * (label_width + 11)) // 2)
        col_width = label_width + 2 + bar_width + 9

        for i in range(half):
            if row >= max_y:
                break

            left_name = cores[i]
            left_usage = calculate_cpu_usage(
                curr_cpu_stats[left_name],
                prev_cpu_stats.get(left_name, (0, 0)),
            )
            safe_addstr(stdscr, row, 2, f"{left_name.upper():<{label_width}}: ")
            draw_bar(stdscr, row, 2 + label_width + 2, left_usage, bar_width)

            j = i + half
            if j < len(cores):
                rc = 2 + col_width + 2
                right_name = cores[j]
                right_usage = calculate_cpu_usage(
                    curr_cpu_stats[right_name],
                    prev_cpu_stats.get(right_name, (0, 0)),
                )
                safe_addstr(stdscr, row, rc, f"{right_name.upper():<{label_width}}: ")
                draw_bar(stdscr, row, rc + label_width + 2, right_usage, bar_width)
            row += 1

        # ── Uptime / Load (right-aligned) ───────────────────────
        if row < max_y:
            header = f"Uptime: {get_uptime()}  Load: {get_loadavg()}"
            safe_addstr(
                stdscr,
                row,
                max(0, max_x - len(header) - 1),
                header,
                curses.color_pair(4),
            )
            row += 1

        # ── Memory / Swap bars ──────────────────────────────────
        mem_total, mem_avail, swap_total, swap_free = get_memory_info()
        mem_used = mem_total - mem_avail
        mem_pct = (mem_used / mem_total) * 100 if mem_total else 0
        swap_used = swap_total - swap_free
        swap_pct = (swap_used / swap_total) * 100 if swap_total else 0

        mus = format_kb(mem_used)
        mts = format_kb(mem_total)
        sus = format_kb(swap_used)
        sts = format_kb(swap_total)
        vw = max(len(mus), len(mts), len(sus), len(sts))

        if row < max_y:
            lbl = f"  Mem: {mus:>{vw}}/{mts:>{vw}} "
            safe_addstr(stdscr, row, 0, lbl)
            draw_bar(stdscr, row, len(lbl), mem_pct, 20)
            row += 1

        if row < max_y:
            lbl = f"  Swp: {sus:>{vw}}/{sts:>{vw}} "
            safe_addstr(stdscr, row, 0, lbl)
            draw_bar(stdscr, row, len(lbl), swap_pct, 20)
            row += 1

        # ── Separator + column header ───────────────────────────
        sep = "=" * (max_x - 1)
        name_width = max(4, max_x - 57)

        if row < max_y:
            safe_addstr(stdscr, row, 0, sep, curses.color_pair(4))
            row += 1

        if row < max_y:
            hdr = (
                f"{'PID':>7} | {'USER':<12} | {'%CPU':>6} | "
                f"{'%MEM':>6} | {'STATE':^5} | {'NAME':<{name_width}}"
            )
            safe_addstr(stdscr, row, 0, hdr, curses.A_BOLD | curses.color_pair(4))
            row += 1

        if row < max_y:
            safe_addstr(stdscr, row, 0, sep, curses.color_pair(4))
            row += 1

        # ── Build process list ──────────────────────────────────
        pids = [p for p in os.listdir("/proc") if p.isdigit()]
        display_list = []
        curr_procs_state = {}
        sys_total_delta = max(1, agg_curr[0] - agg_prev[0])

        for pid in pids:
            proc = get_process_info(pid)
            if not proc:
                continue
            pid_int = int(proc["pid"])
            prev_ticks = prev_procs.get(pid_int)
            if prev_ticks is not None:
                proc["cpu_usage"] = (
                    (proc["ticks"] - prev_ticks) / sys_total_delta
                ) * 100 * cpu_count
            else:
                proc["cpu_usage"] = 0.0
            curr_procs_state[pid_int] = proc["ticks"]
            display_list.append(proc)

        display_list.sort(key=lambda x: x["cpu_usage"], reverse=True)

        # ── Draw process rows ───────────────────────────────────
        footer_rows = 2
        max_proc_rows = max(0, max_y - row - footer_rows)

        for proc in display_list[:max_proc_rows]:
            if row >= max_y - footer_rows:
                break

            user = get_user(proc["uid"], user_cache)
            name = proc["name"]
            pmem = (proc["rss"] / mem_total) * 100 if mem_total else 0

            if len(user) > 12:
                user = user[:11] + "~"
            if len(name) > name_width:
                name = name[: name_width - 1] + "~"

            line = (
                f"{proc['pid']:>7} | {user:<12} | {proc['cpu_usage']:>5.1f}% "
                f"| {pmem:>5.1f}% | {proc['state']:^5} | {name:<{name_width}}"
            )

            if proc["cpu_usage"] > 50:
                attr = curses.color_pair(3) | curses.A_BOLD
            elif proc["cpu_usage"] > 10:
                attr = curses.color_pair(2)
            else:
                attr = curses.color_pair(1)

            safe_addstr(stdscr, row, 0, line, attr)
            row += 1

        # ── Footer ──────────────────────────────────────────────
        footer_row = max_y - 2
        if footer_row >= row and footer_row < max_y:
            safe_addstr(stdscr, footer_row, 0, sep, curses.color_pair(4))
        if footer_row + 1 < max_y:
            status = (
                f" Tasks: {len(display_list)} | "
                "R=Run S=Sleep D=Disk Z=Zombie T=Stop | q=Quit"
            )
            safe_addstr(stdscr, footer_row + 1, 0, status, curses.A_BOLD)

        stdscr.refresh()

        prev_cpu_stats = curr_cpu_stats
        prev_procs = curr_procs_state

        key = stdscr.getch()
        if key == ord("q"):
            break
        elif key == curses.KEY_RESIZE:
            stdscr.clear()


if __name__ == "__main__":
    curses.wrapper(main)