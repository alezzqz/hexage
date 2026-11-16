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
prefix="/usr/local"
binary="${project_root}/dist/linux/hexage"
with_desktop=1
uninstall=0
need_root=0

usage() {
    cat <<'EOF'
Usage: scripts/install-linux.sh [options]

  --prefix DIR    Install under DIR (default: /usr/local).
  --binary PATH   Binary to install (default: dist/linux/hexage).
  --no-desktop    Do not install the icon and the desktop entry.
  --uninstall     Remove files installed by this script.
  -h, --help      Show this help.
EOF
}

run_root() {
    if [[ "$need_root" == 1 ]]; then
        sudo -- "$@"
    else
        "$@"
    fi
}

prepare_root() {
    if [[ "${EUID}" -eq 0 ]]; then
        need_root=0
    elif [[ -w "$prefix" || ( ! -e "$prefix" && -w "$(dirname -- "$prefix")" ) ]]; then
        need_root=0
    else
        need_root=1
        if ! command -v sudo >/dev/null 2>&1; then
            printf 'Root is required for %s; install sudo or run as root.\n' \
                "$prefix" >&2
            exit 1
        fi
        printf 'Using sudo to install into %s.\n' "$prefix" >&2
        if ! sudo -v; then
            printf '%s\n' 'Could not obtain sudo privileges.' >&2
            exit 1
        fi
    fi
}

refresh_desktop_database() {
    if command -v update-desktop-database >/dev/null 2>&1; then
        run_root update-desktop-database "$prefix/share/applications" \
            >/dev/null 2>&1 || true
    fi
}

write_desktop_file() {
    local exec_path="$prefix/bin/hexage" escaped
    escaped=${exec_path//\\/\\\\}
    escaped=${escaped//\"/\\\"}
    cat <<EOF
[Desktop Entry]
Type=Application
Name=Hexage
Comment=Зашифрованные заметки
Exec="$escaped"
Icon=hexage
Terminal=false
Categories=Utility;TextEditor;
EOF
}

install_desktop() {
    local icon="$project_root/hexage/assets/hexage-256.png" tmp
    if [[ -f "$icon" ]]; then
        run_root install -Dm644 -- "$icon" \
            "$prefix/share/icons/hicolor/256x256/apps/hexage.png"
    else
        printf 'Warning: icon not found: %s\n' "$icon" >&2
    fi
    tmp=$(mktemp)
    write_desktop_file >"$tmp"
    run_root install -Dm644 -- "$tmp" \
        "$prefix/share/applications/hexage.desktop"
    rm -f -- "$tmp"
    refresh_desktop_database
}

install_files() {
    if [[ ! -f "$binary" ]]; then
        printf 'Binary not found: %s\n' "$binary" >&2
        printf '%s\n' 'Build it first with scripts/build-linux.sh.' >&2
        exit 1
    fi
    if [[ ! -x "$binary" ]]; then
        printf 'Binary is not executable: %s\n' "$binary" >&2
        exit 1
    fi
    run_root install -Dm755 -- "$binary" "$prefix/bin/hexage"
    run_root install -Dm644 -- "$project_root/LICENSE" \
        "$prefix/share/doc/hexage/LICENSE"
    run_root install -Dm644 -- "$project_root/LICENSE.GPL-3.0" \
        "$prefix/share/doc/hexage/LICENSE.GPL-3.0"
    if [[ "$with_desktop" == 1 ]]; then
        install_desktop
    fi
}

remove_files() {
    run_root rm -f -- "$prefix/bin/hexage"
    run_root rm -f -- "$prefix/share/applications/hexage.desktop"
    run_root rm -f -- "$prefix/share/icons/hicolor/256x256/apps/hexage.png"
    run_root rm -rf -- "$prefix/share/doc/hexage"
    run_root rmdir --ignore-fail-on-non-empty -- \
        "$prefix/share/icons/hicolor/256x256/apps" 2>/dev/null || true
    refresh_desktop_database
    printf 'Removed Hexage from %s.\n' "$prefix"
}

hint_path() {
    case ":${PATH:-}:" in
        *":$prefix/bin:"*) ;;
        *)
            printf 'Add %s to PATH to run "hexage" directly.\n' "$prefix/bin"
            ;;
    esac
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prefix)
            if [[ $# -lt 2 ]]; then
                printf '%s\n' '--prefix requires a path.' >&2
                exit 2
            fi
            prefix=$2
            shift
            ;;
        --binary)
            if [[ $# -lt 2 ]]; then
                printf '%s\n' '--binary requires a path.' >&2
                exit 2
            fi
            binary=$2
            shift
            ;;
        --no-desktop)
            with_desktop=0
            ;;
        --uninstall)
            uninstall=1
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

if ! command -v install >/dev/null 2>&1; then
    printf '%s\n' 'The install command from coreutils is required.' >&2
    exit 1
fi

prefix=$(realpath -m -- "$prefix")
binary=$(realpath -m -- "$binary")

if [[ "$prefix" == "/" ]]; then
    printf '%s\n' 'Refusing to use / as the install prefix.' >&2
    exit 1
fi

if [[ "$uninstall" == 1 ]]; then
    if [[ ! -e "$prefix/bin/hexage" && ! -e "$prefix/share/doc/hexage" ]]; then
        printf 'Hexage is not installed in %s.\n' "$prefix"
        exit 0
    fi
    prepare_root
    remove_files
    exit 0
fi

prepare_root
install_files
printf 'Installed Hexage to %s\n' "$prefix/bin/hexage"
hint_path
