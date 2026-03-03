# Kannon

An educational recreation of `htop` built to understand Linux internals. Parses the `/proc` filesystem directly without relying on external libraries like `psutil`.

## Demo

![demo](assets/kannon-demo.svg)

## Features

- Per-core CPU bars and memory/swap usage
- Process list with CPU%, MEM%, cumulative time, state
- Sortable by CPU / Memory / PID / Time
- Scrollable list with selection cursor
- Kill processes with signal menu
- Search/filter

## Requirements

- Python 3.6+
- Linux


## Usage

```bash
python3 kannon.py
```

or

```bash
chmod +x kannon.py
./kannon.py
```

## Keybindings

| Key                     | Action                              |
| ----------------------- | ----------------------------------- |
| `q`                     | Quit                                |
| `p`                     | Sort by CPU usage                   |
| `m`                     | Sort by memory usage                |
| `n`                     | Sort by PID                         |
| `t`                     | Sort by cumulative time             |
| `↑` / `↓`               | Move selection cursor               |
| `Page Up` / `Page Down` | Scroll one page                     |
| `Home` / `End`          | Jump to top / bottom                |
| `k`                     | Kill selected process (signal menu) |
| `/`                     | Start live search                   |
| `Enter`                 | Confirm search                      |
| `Escape`                | Cancel search                       |
| `\`                     | Clear search filter                 |


## Data Sources

| Data          | Source                                   |
| ------------- | ---------------------------------------- |
| Process stats | `/proc/<pid>/stat`, `/proc/<pid>/status` |
| CPU times     | `/proc/stat`                             |
| Memory        | `/proc/meminfo`                          |
| Uptime & load | `/proc/uptime`, `/proc/loadavg`          |

