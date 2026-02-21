#!/usr/bin/env python3
# listing all running processes by reading /proc

import os
import time
import pwd
import shutil


while True:
    os.system("clear")
    cols = shutil.get_terminal_size().columns
    name_width = cols - 40

    # header
    print(f"{'PID':>7} | {'USER':<12} | {'STATE':^5} | {'NAME':<{name_width}}")
    print("=" * (cols - 1))

    for entry in sorted(
        os.listdir("/proc"), key=lambda x: int(x) if x.isdigit() else 0
    ):
        if entry.isdigit():
            try:
                with open(f"/proc/{entry}/stat") as f:
                    content = f.read()

                first_paran = content.find("(")
                last_paran = content.rfind(")")

                # instead of using /proc/:pid/comm, we can just
                # use /proc/:pid/stat to get it
                name = content[first_paran + 1: last_paran]

                fields = content[last_paran + 2:].split()
                state = fields[0]
                # utime = fields[11], stime = fields[12], starttime = fields[19]

                with open(f"/proc/{entry}/status") as f:
                    for line in f:
                        if line.startswith("Uid:"):
                            # print(f">>> {line.strip()}")
                            uid = int(line.split()[1])
                            # print(f">>> uid={uid}")
                            break

                try:
                    user = pwd.getpwuid(uid).pw_name

                    if len(user) > 12:
                        user = user[:11] + "…"
                    if len(name) > name_width:
                        name = name[:name_width - 1] + "…"

                    # print(f">>> pwd entry: {pwd.getpwuid(uid)}")
                except KeyError:
                    user = str(uid)

                print(f"{entry:>7} | {user:<12} | {state:^5} | {name:<20}")

            except (PermissionError, FileNotFoundError, ValueError, IndexError):
                pass
    print("=" * (cols - 1))
    # im not using all states specified in manfile `proc_pid_stat(5)`
    # these should suffice for now i believe
    print("States: R=Running S=Sleeping D=Disk Z=Zombie T=Stopped")
    time.sleep(1)
