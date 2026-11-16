#!/usr/bin/env bash
# Copyright (C) 2026 TermoGRAF
# SPDX-License-Identifier: LGPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License and
# the GNU General Public License along with this program. If not, see
# <https://www.gnu.org/licenses/>.

set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$project_root"

mode=install
python="${HEXAGE_PYTHON:-python3}"
python_from_option=0

PROBE_FONTSYSTEM='import tkinter as tk
root = tk.Tk()
print(root.tk.eval("tk::pkgconfig get fontsystem"))
root.destroy()'

usage() {
    cat <<'EOF'
Usage: scripts/setup-linux.sh [--check | --build] [--python PATH]

  --check        Only check Python, tkinter, and the Tk font system.
  --build        Create .venv and install the build extras as well.
  --python PATH  Interpreter to use (default: python3 or $HEXAGE_PYTHON).
  -h, --help     Show this help.
EOF
}

print_packages() {
    cat >&2 <<'EOF'
Install Python and Tk for the distribution:
  Ubuntu/Debian  sudo apt install python3 python3-venv python3-tk
  Fedora         sudo dnf install python3 python3-tkinter
  Arch           sudo pacman -S python tk
Use the system Python, not a uv-managed build, so tkinter uses system Tk.
With uv: uv venv --python /usr/bin/python3.12
EOF
}

check_python() {
    if ! command -v "$python" >/dev/null 2>&1; then
        printf 'Python interpreter not found: %s\n' "$python" >&2
        print_packages
        exit 1
    fi
    if ! "$python" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'; then
        printf 'Python 3.11 or newer is required, found %s (%s).\n' \
            "$("$python" -c 'import sys; print(sys.version.split()[0])')" \
            "$python" >&2
        print_packages
        exit 1
    fi
    local version
    version=$("$python" -c \
        'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if [[ "$version" != 3.11 && "$version" != 3.12 && "$version" != 3.13 ]]; then
        printf 'Warning: Hexage is tested on Python 3.11-3.13; found %s.\n' \
            "$version" >&2
    fi
}

check_tkinter() {
    if ! "$python" -c 'import tkinter' >/dev/null 2>&1; then
        printf 'tkinter is missing for %s.\n' "$python" >&2
        print_packages
        exit 1
    fi
}

probe_fontsystem() {
    "$1" -c "$PROBE_FONTSYSTEM"
}

check_fontsystem() {
    local interpreter=$1 fontsystem
    if fontsystem=$(probe_fontsystem "$interpreter" 2>/dev/null); then
        :
    elif command -v xvfb-run >/dev/null 2>&1 &&
        fontsystem=$(xvfb-run -a "$interpreter" -c "$PROBE_FONTSYSTEM" 2>/dev/null); then
        :
    else
        printf '%s\n' \
            'Warning: cannot query the Tk font system without a display.' >&2
        return 0
    fi
    if [[ "$fontsystem" != xft ]]; then
        printf 'Tk has no Xft support (fontsystem=%s).\n' "$fontsystem" >&2
        printf '%s\n' \
            'If .venv was created by a different Python, remove it and rerun.' \
            >&2
        print_packages
        exit 1
    fi
    printf 'Tk font system: xft\n'
}

create_venv() {
    if [[ ! -x .venv/bin/python ]]; then
        "$python" -m venv .venv
    else
        printf '%s\n' 'Using existing .venv.'
    fi
    local extras='.[dev]'
    if [[ "$mode" == build ]]; then
        extras='.[dev,build]'
    fi
    if .venv/bin/python -m pip --version >/dev/null 2>&1; then
        .venv/bin/python -m pip install -e "$extras"
    elif command -v uv >/dev/null 2>&1; then
        uv pip install --python .venv/bin/python -e "$extras"
    elif .venv/bin/python -m ensurepip --upgrade >/dev/null 2>&1; then
        .venv/bin/python -m pip install -e "$extras"
    else
        printf '%s\n' \
            'No pip in .venv and uv is not available.' \
            'Create the venv with "python -m venv .venv" or install uv.' >&2
        exit 1
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --check)
            mode=check
            ;;
        --build)
            mode=build
            ;;
        --python)
            if [[ $# -lt 2 ]]; then
                printf '%s\n' '--python requires a path.' >&2
                exit 2
            fi
            python=$2
            python_from_option=1
            shift
            ;;
        -h | --help)
            usage
            exit 0
            ;;
        *)
            printf 'Unknown option: %s\n' "$1" >&2
            usage >&2
            exit 2
            ;;
    esac
    shift
done

if [[ "$python_from_option" == 0 && -x .venv/bin/python ]]; then
    python=.venv/bin/python
fi

check_python
check_tkinter

if [[ "$mode" == check ]]; then
    check_fontsystem "$python"
    printf 'Environment OK for %s.\n' "$python"
    exit 0
fi

create_venv
check_fontsystem .venv/bin/python

printf '%s\n' \
    'Setup complete.' \
    '  .venv/bin/python -m hexage' \
    '  .venv/bin/python -m pytest'
if [[ "$mode" == build ]]; then
    printf '%s\n' '  bash scripts/build-linux.sh'
fi
