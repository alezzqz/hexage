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

"$python" -m PyInstaller --noconfirm --onefile --noupx --name hexage \
    --distpath dist/linux --workpath build/linux --specpath build/linux \
    --collect-data hexage scripts/hexage_entry.py

cp LICENSE LICENSE.GPL-3.0 dist/linux/

printf '%s\n' 'Built dist/linux/hexage with license files'
