#!/usr/bin/env python3
# listing all running processes by reading /proc

import os
import time
import pwd
import shutil

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
        # utime = fields[11], stime = fields[12], starttime = fields[19]

        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("Uid:"):
                    # print(f">>> {line.strip()}")
                    uid = int(line.split()[1])
                    # print(f">>> uid={uid}")
                    break

        try:
            user = pwd.getpwuid(uid).pw_name
            # print(f">>> pwd entry: {pwd.getpwuid(uid)}")
        except KeyError:
            user = str(uid)

        return {
            "pid": pid,
            "name": name,
            "state": fields[0],
            "ppid": fields[1],
            "user": user
        }

    except (PermissionError, FileNotFoundError, ValueError, IndexError):
        return None


while True:
    cols = shutil.get_terminal_size().columns
    name_width = cols - 40
    os.system("clear")

    # header
    print(f"{'PID':>7} | {'USER':<12} | {'STATE':^5} | {'NAME':<{name_width}}")
    print("=" * (cols - 1))

    pids = [p for p in os.listdir("/proc") if p.isdigit()]

    for pid in sorted(pids, key=int):
        proc = get_process_info(pid)
        
        if not proc:
            continue
        
        p_user = proc['user']
        p_name = proc['name']

        if len(p_user) > 12:
            p_user = p_user[:11] + "…"
        if len(p_name) > name_width:
            p_name = p_name[:name_width - 1] + "…"

        
        print(f"{proc['pid']:>7} | {p_user:<12} | {proc['state']:^5} | {p_name:<20}")
            
    print("=" * (cols - 1))
    # im not using all states specified in manfile `proc_pid_stat(5)`
    # these should suffice for now i believe
    print("States: R=Running S=Sleeping D=Disk Z=Zombie T=Stopped")
    time.sleep(1)
