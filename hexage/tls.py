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

"""TLS defaults for the OpenSSL build shipped with Hexage."""

import os
import sys


def apply_openssl_defaults(platform: str = sys.platform) -> None:
    """Ignore distribution OpenSSL configuration unless the user set one.

    Linux builds embed OpenSSL 3.5, which refuses to create any TLS context when
    the distribution openssl.cnf enables config_diagnostics and contains a
    directive that this OpenSSL version rejects. On such systems every HTTPS
    request fails, so cloud storage reports a connection error right after the
    browser login. urllib3 creates a context while it is imported, and OpenSSL
    keeps the failed state for the whole process, so the variable has to be set
    before the package imports requests. Windows has no distribution config.
    """
    if not platform.startswith("linux"):
        return
    os.environ.setdefault("OPENSSL_CONF", os.devnull)
