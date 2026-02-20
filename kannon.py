#!/usr/bin/env python3
# listing all running processes by reading /proc

import os
import time

while True:
    for entry in os.listdir('/proc'):
        if (entry.isdigit()):
            try:
                with open(f"/proc/{entry}/comm") as f:
                    name = f.read().strip()
                print(f"{entry:>6} | {name}")
            except (PermissionError, FileNotFoundError):
                pass
    print("=" * 50)
    time.sleep(1)
