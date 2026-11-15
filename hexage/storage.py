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

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import portalocker
from platformdirs import user_data_path

from .codec import MAX_FILE
from .model import HexageError, identifier


def default_path() -> Path:
    return user_data_path("Hexage", appauthor=False) / "vault.hexage"


def read_file(path: Path) -> bytes:
    with path.open("rb") as source:
        blob = source.read(MAX_FILE + 1)
    if len(blob) > MAX_FILE:
        raise HexageError("Превышен предел размера контейнера.")
    return blob


def fingerprint(blob: bytes) -> bytes:
    return hashlib.sha256(blob).digest()


def sync_directory(path: Path) -> None:
    if os.name == "posix":
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def write_atomic(path: Path, blob: bytes, *, replace: bool) -> bool:
    descriptor, name = tempfile.mkstemp(dir=path.parent, prefix=".hexage-")
    staged = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as target:
            target.write(blob)
            target.flush()
            os.fsync(target.fileno())
        if replace:
            os.replace(staged, path)
        else:
            os.link(staged, path)
        try:
            sync_directory(path.parent)
        except OSError:
            # The new file is already visible. Report reduced durability to the caller.
            return False
        return True
    finally:
        try:
            staged.unlink(missing_ok=True)
        except OSError:
            pass  # A leftover temporary file contains only encrypted bytes.


@dataclass(frozen=True)
class Commit:
    digest: bytes
    durable: bool


@dataclass(frozen=True)
class Store:
    path: Path

    def read(self) -> bytes | None:
        try:
            return read_file(self.path)
        except FileNotFoundError:
            return None

    def commit(
        self, blob: bytes, expected: bytes | None, *, backup: bool = False
    ) -> Commit:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        lock = self.path.with_suffix(".lock")
        try:
            with portalocker.Lock(lock, mode="a", timeout=1):
                return self._commit_locked(blob, expected, backup)
        except portalocker.exceptions.LockException:
            raise HexageError("Хранилище занято другим экземпляром Hexage.") from None

    def _commit_locked(
        self, blob: bytes, expected: bytes | None, backup: bool
    ) -> Commit:
        current = self.read()
        digest = fingerprint(current) if current is not None else None
        if digest != expected:
            raise HexageError(
                "Активный файл изменился. Заблокируйте и снова откройте его."
            )
        if backup and current is not None:
            path = self.path.with_name(f"backup-{identifier()}.hexage")
            if not write_atomic(path, current, replace=False):
                raise HexageError("Не удалось подтвердить запись резервной копии.")
            self.snapshot(expected)
        return Commit(
            fingerprint(blob),
            write_atomic(self.path, blob, replace=current is not None),
        )

    def export(self, path: Path, expected: bytes) -> bool:
        return write_atomic(path, self.snapshot(expected), replace=False)

    def snapshot(self, expected: bytes) -> bytes:
        blob = self.read()
        if blob is None or fingerprint(blob) != expected:
            raise HexageError("Активный файл изменился. Снова откройте хранилище.")
        return blob
