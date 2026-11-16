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

if [[ "$(uname -s)" != Linux ]]; then
    printf '%s\n' 'Build the Linux binary on Linux.' >&2
    exit 1
fi

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$project_root"
python="${HEXAGE_BUILD_PYTHON:-.venv/bin/python}"

allow_legacy=0
if [[ "${HEXAGE_ALLOW_LEGACY_TK:-0}" == 1 ]]; then
    allow_legacy=1
fi

usage() {
    printf '%s\n' \
        'Usage: bash scripts/build-linux.sh [--allow-legacy-tk]' \
        '' \
        '  --allow-legacy-tk  Build even if the build Python uses Tk without Xft.'
}

check_xft() {
    if [[ "$allow_legacy" == 1 ]]; then
        printf '%s\n' 'Warning: building with legacy X11 fonts by request.' >&2
        return
    fi
    local tkinter tk_lib
    tkinter=$("$python" -c 'import _tkinter; print(_tkinter.__file__)' \
        2>/dev/null) || return 0
    tk_lib=$(ldd "$tkinter" 2>/dev/null |
        awk '/libtcl.*tk|libtk/ { print $3; exit }')
    if [[ -z "$tk_lib" || ! -f "$tk_lib" ]]; then
        printf '%s\n' \
            'Warning: could not locate the Tk library; Xft support not verified.' \
            >&2
        return
    fi
    if ! objdump -p "$tk_lib" 2>/dev/null | grep -q 'NEEDED.*libXft'; then
        printf '%s\n' \
            'Error: this Python Tk has no Xft support, so the binary would use' \
            'legacy X11 fonts. Use a Python built against Tk with Xft, or pass' \
            '--allow-legacy-tk to build anyway.' >&2
        exit 1
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --allow-legacy-tk)
            allow_legacy=1
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

check_xft

"$python" -m PyInstaller --noconfirm --onefile --noupx --name hexage \
    --distpath dist/linux --workpath build/linux --specpath build/linux \
    --collect-data hexage scripts/hexage_entry.py

cp LICENSE LICENSE.GPL-3.0 dist/linux/

printf '%s\n' 'Built dist/linux/hexage with license files'
