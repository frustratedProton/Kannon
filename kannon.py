#!/usr/bin/env python3
# listing all running processes by reading /proc

import os
import time
import pwd

while True:
    os.system("clear")

    # header
    print(f"{'PID':>7} | {'USER':<12} | {'NAME':<20}")
    print("-" * 45)

    for entry in sorted(
        os.listdir("/proc"), key=lambda x: int(x) if x.isdigit() else 0
    ):
        if entry.isdigit():
            try:
                with open(f"/proc/{entry}/comm") as f:
                    name = f.read().strip()

                with open(f"/proc/{entry}/status") as f:
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

                print(f"{entry:>7} | {user:<12} | {name:<20}")

            except (PermissionError, FileNotFoundError):
                pass
    print("=" * 50)
    time.sleep(1)
