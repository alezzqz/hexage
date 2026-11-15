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

import binascii
import secrets
import struct
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .crypto import PROFILE, Keys, derive_keys, new_phrase, wrapping_key
from .model import HexageError, Vault, encode_vault, new_vault, parse_vault

MAX_FILE = 16 * 1024 * 1024
HEADER = struct.Struct(">4sBBBIBB16s12s12sI")
WRAPPED_SIZE = 60
TAG_SIZE = 16
FORMAT = (b"HXGE", 1, 1, 1)
WRAP = b"Hexage/v1/wrap"
DATA = b"Hexage/v1/data"


@dataclass(frozen=True, repr=False)
class OpenVault:
    vault: Vault
    keys: Keys
    salt: bytes

    def with_password(self, password: str) -> "OpenVault":
        salt = secrets.token_bytes(16)
        keys = derive_keys(self.keys.phrase, wrapping_key(password, salt))
        return OpenVault(self.vault.advance(self.vault.notes), keys, salt)


def create(password: str) -> OpenVault:
    salt = secrets.token_bytes(16)
    return OpenVault(
        new_vault(), derive_keys(new_phrase(), wrapping_key(password, salt)), salt
    )


def read_header(blob: bytes) -> tuple[bytes, bytes, bytes, bytes]:
    if not HEADER.size + WRAPPED_SIZE + TAG_SIZE <= len(blob) <= MAX_FILE:
        raise HexageError("Недопустимый размер контейнера.")
    header = blob[: HEADER.size]
    magic, version, cipher, kdf, memory, passes, lanes, salt, wn, dn, size = (
        HEADER.unpack(header)
    )
    if (magic, version, cipher, kdf) != FORMAT:
        raise HexageError("Неподдерживаемый формат или алгоритм контейнера.")
    if (memory, passes, lanes) != PROFILE:
        raise HexageError("Неподдерживаемые параметры Argon2id.")
    if size != len(blob) - HEADER.size - WRAPPED_SIZE:
        raise HexageError("Повреждён заголовок контейнера.")
    return header, salt, wn, dn


def open_vault(blob: bytes, password: str) -> OpenVault:
    header, salt, wrap_nonce, data_nonce = read_header(blob)
    wrapping = wrapping_key(password, salt)
    split = HEADER.size + WRAPPED_SIZE
    wrapped = blob[HEADER.size : split]
    try:
        phrase = AESGCM(wrapping).decrypt(wrap_nonce, wrapped, WRAP + header)
        keys = derive_keys(phrase, wrapping)
        data = AESGCM(keys.data).decrypt(
            data_nonce, blob[split:], DATA + header + wrapped
        )
    except (InvalidTag, ValueError, binascii.Error):
        raise HexageError("Неверный пароль или контейнер повреждён.") from None
    return OpenVault(parse_vault(data), keys, salt)


def seal(opened: OpenVault) -> bytes:
    raw = encode_vault(opened.vault)
    size = len(raw) + TAG_SIZE
    if HEADER.size + WRAPPED_SIZE + size > MAX_FILE:
        raise HexageError("Превышен предел размера контейнера.")
    wn, dn = secrets.token_bytes(12), secrets.token_bytes(12)
    header = HEADER.pack(*FORMAT, *PROFILE, opened.salt, wn, dn, size)
    wrapped = AESGCM(opened.keys.wrapping).encrypt(
        wn, opened.keys.phrase, WRAP + header
    )
    data = AESGCM(opened.keys.data).encrypt(dn, raw, DATA + header + wrapped)
    return header + wrapped + data
