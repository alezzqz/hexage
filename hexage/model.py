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

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

HISTORY = 256


class HexageError(Exception):
    """An error whose message is safe to show in the UI."""


def identifier() -> str:
    return uuid4().hex


@dataclass(frozen=True)
class Note:
    id: str
    title: str
    text: str


@dataclass(frozen=True)
class Vault:
    vault: str
    revision: str
    ancestors: tuple[str, ...]
    changed: str
    notes: tuple[Note, ...]

    def advance(self, notes: tuple[Note, ...]) -> "Vault":
        return Vault(
            self.vault,
            identifier(),
            (self.revision, *self.ancestors[: HISTORY - 1]),
            utc_now(),
            notes,
        )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def new_vault() -> Vault:
    return Vault(identifier(), identifier(), (), utc_now(), ())


def valid_id(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch("[a-f0-9]{32}", value))


def valid_text(value: object, limit: int) -> bool:
    return isinstance(value, str) and len(value.encode("utf-8")) <= limit


def parse_note(value: dict) -> Note:
    note = Note(**value)
    if not (
        valid_id(note.id)
        and valid_text(note.title, 4096)
        and note.title.strip()
        and valid_text(note.text, 4194304)
    ):
        raise ValueError
    return note


def parse_vault(raw: bytes) -> Vault:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_fields)
        if not isinstance(value["ancestors"], list) or not isinstance(
            value["notes"], list
        ):
            raise ValueError
        if len(value["ancestors"]) > HISTORY or len(value["notes"]) > 10000:
            raise ValueError
        value["ancestors"] = tuple(value["ancestors"])
        value["notes"] = tuple(parse_note(note) for note in value["notes"])
        vault = Vault(**value)
        ids = (vault.revision, *vault.ancestors)
        if not valid_id(vault.vault) or not all(map(valid_id, ids)):
            raise ValueError
        if len(set(ids)) != len(ids) or len({n.id for n in vault.notes}) != len(
            vault.notes
        ):
            raise ValueError
        date = datetime.fromisoformat(vault.changed)
        if (
            date.astimezone(timezone.utc).isoformat(timespec="microseconds")
            != vault.changed
        ):
            raise ValueError
        return vault
    except (ValueError, TypeError, KeyError, RecursionError, OverflowError):
        raise HexageError("Недопустимые данные хранилища.") from None


def unique_fields(pairs: list[tuple[str, object]]) -> dict:
    fields = dict(pairs)
    if len(fields) != len(pairs):
        raise ValueError
    return fields


def encode_vault(vault: Vault) -> bytes:
    try:
        data = json.dumps(
            asdict(vault), ensure_ascii=False, separators=(",", ":")
        ).encode()
    except UnicodeError:
        raise HexageError("Недопустимый текст заметки.") from None
    parse_vault(data)
    return data


class Relation(Enum):
    NEW = "Активного файла пока нет."
    SAME = "Снимок уже актуален."
    INCONSISTENT = "Одинаковая ревизия содержит разные данные."
    OLDER = "Снимок — предок активной ревизии."
    NEWER = "Снимок — потомок активной ревизии с более поздней датой."
    CONFLICT = "Ветвление, противоречие истории и дат или неизвестный порядок."
    OTHER = "Снимок относится к другому хранилищу."


def compare(local: Vault | None, incoming: Vault) -> Relation:
    if local is None:
        return Relation.NEW
    if local.vault != incoming.vault:
        return Relation.OTHER
    if local.revision == incoming.revision:
        return Relation.SAME if local == incoming else Relation.INCONSISTENT
    if incoming.revision in local.ancestors:
        return Relation.OLDER
    if local.revision in incoming.ancestors and incoming.changed > local.changed:
        return Relation.NEWER
    return Relation.CONFLICT
