#!/usr/bin/env python3

import os
import time
import pwd
import shutil

def draw_bar(percent, width=20):
    """Returns a colored bar string like '[|||||     ] 50.0%'"""
    percent = max(0.0, min(100.0, percent))
    fill = int(width * (percent / 100))
    empty = width - fill

    color = "\033[92m"  # green
    if percent > 50:
        color = "\033[93m"  # yellow
    if percent > 80:
        color = "\033[91m"  # red

    return f"[{color}{'|' * fill}{' ' * empty}\033[0m] {percent:>5.1f}%"


def calculate_cpu_usage(curr, prev):# -> float | Any:
    """Calculate CPU usage % from two (total, idle) snapshots
    Returns: 
    """
    total_d = curr[0] - prev[0]
    idle_d = curr[1] - prev[1]
    if total_d <= 0:
        return 0.0
    return ((total_d - idle_d) / total_d) * 100

def get_cpu_stats():# -> dict | None:
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
                    values[0] -= values[8]   # user -= guest
                    values[1] -= values[9]   # nice -= guest_nice

                # Total CPU Time = user + nice + system + idle + iowait + irq + softirq + steal
                total_cpu_time = sum(values[:8])
                # idle + iowait
                idle_cpu_time = values[3] + values[4]

                stats[name] = (total_cpu_time, idle_cpu_time)
            return stats
    except (FileNotFoundError, PermissionError, ValueError):
        return {}

def get_process_info(pid):# -> dict[str, Any] | None:
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
        name = content[first_paran + 1: last_paran]

        fields = content[last_paran + 2:].split()
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
    """Returns (total_kb, available_kb) from /proc/meminfo"""
    total_memory = available_memory = 0
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemTotal:"):
                total_memory = int(line.split()[1])
            elif line.startswith("MemAvailable:"):
                available_memory = int(line.split()[1])
            if total_memory and available_memory:
                break
    return total_memory, available_memory


def format_kb(kb):
    """Formats kB as human-readable string"""
    if kb < 1024:
        return f"{kb}K"
    elif kb < 1024 * 1024:
        return f"{kb / 1024:.1f}M"
    else:
        return f"{kb / (1024 * 1024):.1f}G"


def get_uptime():
    """Returns formatted uptime string"""
    with open("/proc/uptime") as f:
        uptime_seconds = float(f.read().split()[0])
        uptime_hours = int((uptime_seconds % 86400) // 3600)
        uptime_minutes = int((uptime_seconds % 3600) // 60)
        uptime_days = int(uptime_seconds // 86400)

        if uptime_days > 0:
            return f"{uptime_days} days, {uptime_hours:02}:{uptime_minutes:02}:{uptime_seconds:02}"
        return f"{uptime_hours:02}:{uptime_minutes:02}:{uptime_seconds:02}"


def get_loadavg():
    """Returns load average string (1, 5, 15 min)"""
    with open("/proc/loadavg") as f:
        fields = f.read().split()
    return f"{fields[0]} {fields[1]} {fields[2]}"


def main():
    prev_cpu_stats = get_cpu_stats()
    prev_procs = {}
    user_cache = {}
    cpu_count = os.cpu_count() or 1

    while True:
        curr_cpu_stats = get_cpu_stats()
        cols = shutil.get_terminal_size().columns
        rows = shutil.get_terminal_size().lines
        os.system("clear")

        cores = sorted(
            [k for k in curr_cpu_stats if k != "cpu"],
            key=lambda x: int(x.replace("cpu", "")),
        )

        if cores:
            label_width = len(f"CPU{cores[-1].replace('cpu', '')}")
        else:
            label_width = 3
        label_width = max(label_width, 3)

        bar_width = max(5, (cols - 4 - 2 * (label_width + 11)) // 2)

        avg_bar_width = max(5, cols - label_width - 14)

        agg_curr = curr_cpu_stats.get("cpu", (0, 0))
        agg_prev = prev_cpu_stats.get("cpu", (0, 0))
        global_usage = calculate_cpu_usage(agg_curr, agg_prev)
        print(f"  {'AVG':<{label_width}}: {draw_bar(global_usage, avg_bar_width)}")

        half = (len(cores) + 1) // 2

        for i in range(half):
            left_name = cores[i]
            left_usage = calculate_cpu_usage(
                curr_cpu_stats[left_name],
                prev_cpu_stats.get(left_name, (0, 0)),
            )
            left = (
                f"{left_name.upper():<{label_width}}: {draw_bar(left_usage, bar_width)}"
            )

            right = ""
            j = i + half
            if j < len(cores):
                right_name = cores[j]
                right_usage = calculate_cpu_usage(
                    curr_cpu_stats[right_name],
                    prev_cpu_stats.get(right_name, (0, 0)),
                )
                right = f"{right_name.upper():<{label_width}}: {draw_bar(right_usage, bar_width)}"

            print(f"  {left}  {right}")

        uptime = get_uptime()
        loadavg = get_loadavg()
        header = f"Uptime: {uptime}  Load: {loadavg}"
        print(f"{header:>{cols}}")

        mem_total, mem_available = get_memory_info()
        mem_used = mem_total - mem_available
        mem_percent = (mem_used / mem_total) * 100 if mem_total else 0
        mem_bar = draw_bar(mem_percent, 20)
        print(f"  Mem: {format_kb(mem_used)}/{format_kb(mem_total)} {mem_bar}")

        print("=" * cols)

        name_width = cols - 57

        print(
            f"{'PID':>7} | {'USER':<12} | {'%CPU':>6} | {'%MEM':>6} | {'STATE':^5} | {'NAME':<{name_width}}"
        )
        print("=" * cols)

        pids = [p for p in os.listdir("/proc") if p.isdigit()]
        display_list = []
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

        display_list.sort(key=lambda x: x["cpu_usage"], reverse=True)

        header_height = 1 + 1 + half + 3
        max_rows = rows - header_height - 3

        for proc in display_list[:max_rows]:
            user = get_user(proc["uid"], user_cache)
            name = proc["name"]

            mem_percent = (proc["rss"] / mem_total) * 100 if mem_total else 0

            if len(user) > 12:
                user = user[:11] + "…"
            if len(name) > name_width:
                name = name[: name_width - 1] + "…"

            line = (
                f"{proc['pid']:>7} | {user:<12} | {proc['cpu_usage']:>5.1f}% "
                f"| {mem_percent:>5.1f}% | {proc['state']:^5} | {name:<{name_width}}"
            )

            if proc["cpu_usage"] > 50:
                line = f"\033[1;31m{line}\033[0m"

            print(line)

        print("=" * cols)
        print(
            f"Tasks: {len(display_list)} | "
            "States: R=Running S=Sleeping D=Disk Z=Zombie T=Stopped"
        )

        prev_cpu_stats = curr_cpu_stats
        prev_procs = curr_procs_state

        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
