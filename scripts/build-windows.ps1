#Requires -Version 5.1
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

param([string]$Python = "")

$ErrorActionPreference = "Stop"
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw "Build Hexage.exe on Windows."
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$AppIcon = Join-Path $ProjectRoot "hexage\assets\hexage.ico"
if (-not $Python) {
    $Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
}

Push-Location -LiteralPath $ProjectRoot
try {
    & $Python -m PyInstaller --noconfirm --onefile --windowed --noupx --name Hexage `
        --distpath dist/windows --workpath build/windows --specpath build/windows `
        --icon $AppIcon --collect-data hexage scripts/hexage_entry.py
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller exited with code $LASTEXITCODE."
    }
    Copy-Item -LiteralPath (Join-Path $ProjectRoot "LICENSE") `
        -Destination (Join-Path $ProjectRoot "dist\windows")
    Copy-Item -LiteralPath (Join-Path $ProjectRoot "LICENSE.GPL-3.0") `
        -Destination (Join-Path $ProjectRoot "dist\windows")
    Write-Host "Built dist/windows/Hexage.exe with license files"
}
finally {
    Pop-Location
}
