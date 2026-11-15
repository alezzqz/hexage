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

import base64
import secrets
from dataclasses import dataclass

from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .model import HexageError

PROFILE = (65536, 3, 4)


@dataclass(frozen=True, repr=False)
class Keys:
    phrase: bytes
    wrapping: bytes
    data: bytes


def wrapping_key(password: str, salt: bytes) -> bytes:
    try:
        encoded = password.encode("utf-8")
    except UnicodeError:
        raise HexageError("Пароль содержит недопустимые символы.") from None
    if not 1 <= len(encoded) <= 65536:
        raise HexageError("Пароль должен занимать от 1 до 65536 байт UTF-8.")
    memory, passes, lanes = PROFILE
    return hash_secret_raw(
        encoded, salt, passes, memory, lanes, 32, Type.ID, version=19
    )


def new_phrase() -> bytes:
    return base64.urlsafe_b64encode(secrets.token_bytes(32))


def derive_keys(phrase: bytes, wrapping: bytes) -> Keys:
    raw = base64.urlsafe_b64decode(phrase)
    if len(raw) != 32 or base64.urlsafe_b64encode(raw) != phrase:
        raise ValueError
    data = HKDF(hashes.SHA256(), 32, None, b"Hexage/v1/data-key").derive(raw)
    return Keys(phrase, wrapping, data)
