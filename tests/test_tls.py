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

import os
import subprocess
import sys

from hexage import tls


def test_windows_keeps_environment(monkeypatch):
    monkeypatch.setattr(os, "environ", {})
    tls.apply_openssl_defaults("win32")
    assert os.environ == {}


def test_linux_uses_openssl_defaults(monkeypatch):
    monkeypatch.setattr(os, "environ", {})
    tls.apply_openssl_defaults("linux")
    assert os.environ["OPENSSL_CONF"] == os.devnull


def test_existing_configuration_is_kept(monkeypatch):
    monkeypatch.setattr(os, "environ", {"OPENSSL_CONF": "/etc/ssl/openssl.cnf"})
    tls.apply_openssl_defaults("linux")
    assert os.environ["OPENSSL_CONF"] == "/etc/ssl/openssl.cnf"


def test_package_applies_defaults_before_tls_import():
    """The package must set the variable before urllib3 initializes OpenSSL."""
    code = (
        "import os\n"
        "import hexage\n"
        "import ssl\n"
        "print(os.environ.get('OPENSSL_CONF', ''))\n"
        "ssl.create_default_context()\n"
    )
    env = {key: value for key, value in os.environ.items() if key != "OPENSSL_CONF"}
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    expected = os.devnull if sys.platform.startswith("linux") else ""
    assert result.stdout.strip() == expected
