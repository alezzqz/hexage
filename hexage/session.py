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

from dataclasses import dataclass, replace
from hmac import compare_digest

from .codec import OpenVault, create, open_vault, seal
from .crypto import wrapping_key
from .model import HexageError, Note, Relation, compare
from .storage import Commit, Store, fingerprint


@dataclass(frozen=True, repr=False)
class Session:
    opened: OpenVault
    digest: bytes
    durable: bool = True


@dataclass(frozen=True, repr=False)
class RestorePlan:
    opened: OpenVault
    blob: bytes
    expected: bytes | None
    relation: Relation

    def can_apply(self) -> bool:
        return self.relation not in {Relation.SAME, Relation.INCONSISTENT}

    def apply(self, store: Store) -> Session:
        if not self.can_apply():
            raise HexageError(self.relation.value)
        commit = store.commit(self.blob, self.expected, backup=True)
        return committed(self.opened, commit)


def committed(opened: OpenVault, commit: Commit) -> Session:
    return Session(opened, commit.digest, commit.durable)


def unlock(store: Store, password: str) -> Session:
    blob = store.read()
    if blob is None:
        raise HexageError("Активный файл отсутствует.")
    return Session(open_vault(blob, password), fingerprint(blob))


def initialize(store: Store, password: str) -> Session:
    opened = create(password)
    return committed(opened, store.commit(seal(opened), None))


def save(store: Store, session: Session, notes: tuple[Note, ...]) -> Session:
    opened = replace(session.opened, vault=session.opened.vault.advance(notes))
    return committed(opened, store.commit(seal(opened), session.digest))


def change_password(store: Store, session: Session, current: str, new: str) -> Session:
    opened = session.opened
    if not compare_digest(wrapping_key(current, opened.salt), opened.keys.wrapping):
        raise HexageError("Неверный текущий пароль.")
    updated = opened.with_password(new)
    return committed(updated, store.commit(seal(updated), session.digest, backup=True))


def plan_restore(blob: bytes, password: str, local: Session | None) -> RestorePlan:
    incoming = open_vault(blob, password)
    relation = compare(local.opened.vault if local else None, incoming.vault)
    if relation is Relation.SAME and local and incoming.keys != local.opened.keys:
        relation = Relation.INCONSISTENT
    return RestorePlan(incoming, blob, local.digest if local else None, relation)
