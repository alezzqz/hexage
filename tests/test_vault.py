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

from dataclasses import replace
from pathlib import Path

import pytest

from hexage import codec, storage
from hexage.model import HexageError, Note, Relation, identifier
from hexage.session import change_password, initialize, plan_restore, save, unlock
from hexage.storage import Store

PASSWORD = "Тестовый синтетический пароль 🔐"
NOTE = Note("1" * 32, "Тест", "первая строка\n第二行\n")


@pytest.fixture
def active(tmp_path):
    store = Store(tmp_path / "vault.hexage")
    return store, initialize(store, PASSWORD)


def test_roundtrip_and_password_change(active):
    store, session = active
    session = save(store, session, (NOTE,))
    before = store.read()
    with pytest.raises(HexageError):
        change_password(store, session, "incorrect", "new")
    changed = change_password(store, session, PASSWORD, "new")
    assert changed.opened.keys.data == session.opened.keys.data
    assert changed.opened.salt != session.opened.salt
    assert unlock(store, "new").opened.vault.notes == (NOTE,)
    with pytest.raises(HexageError):
        unlock(store, PASSWORD)
    assert codec.open_vault(before, PASSWORD).vault.notes == (NOTE,)
    assert list(store.path.parent.glob("backup-*.hexage"))[0].read_bytes() == before


@pytest.mark.parametrize("index", [0, 4, 5, 6, 8, 16, 40, 56, 58, -1])
def test_corruption(active, index):
    store, _ = active
    blob = bytearray(store.read())
    blob[index] ^= 1
    with pytest.raises(HexageError):
        codec.open_vault(bytes(blob), PASSWORD)


def test_reject_profile_before_kdf(active, monkeypatch):
    store, _ = active
    blob = bytearray(store.read())
    blob[7:11] = b"\xff" * 4
    monkeypatch.setattr(codec, "wrapping_key", lambda *_: pytest.fail("KDF entered"))
    with pytest.raises(HexageError, match="Argon2id"):
        codec.open_vault(bytes(blob), PASSWORD)


@pytest.mark.parametrize("stage", ["write", "backup", "replace"])
def test_required_backup_and_active_file_survive_failures(active, monkeypatch, stage):
    store, session = active
    original = store.read()
    write = storage.write_atomic

    def fail():
        raise OSError("synthetic failure")

    def inject(path, blob, *, replace):
        if (
            stage == "backup"
            and path != store.path
            or stage == "write"
            and path == store.path
        ):
            fail()
        return write(path, blob, replace=replace)

    monkeypatch.setattr(storage, "write_atomic", inject)
    if stage == "replace":
        monkeypatch.setattr(storage.os, "replace", lambda *_: fail())
    with pytest.raises(OSError):
        store.commit(b"encrypted replacement", session.digest, backup=True)
    assert store.read() == original


def test_competing_writers(active):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    store, session = active
    barrier = Barrier(2)

    def attempt():
        barrier.wait(timeout=3)
        try:
            return save(store, session, (NOTE,))
        except HexageError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(attempt) for _ in range(2)]
        accepted = [job.result() for job in jobs if job.result() is not None]
    assert len(accepted) == 1
    assert unlock(store, PASSWORD).digest == accepted[0].digest


@pytest.mark.parametrize(
    ("kind", "expected", "restorable"),
    [
        ("new", Relation.NEW, True),
        ("same", Relation.SAME, False),
        ("mutated", Relation.INCONSISTENT, False),
        ("old", Relation.OLDER, True),
        ("newer", Relation.NEWER, True),
        ("branch", Relation.CONFLICT, True),
        ("clock", Relation.CONFLICT, True),
        ("other", Relation.OTHER, True),
    ],
)
def test_restore_decisions(active, kind, expected, restorable):
    store, initial = active
    local = save(store, initial, (NOTE,))
    current = local.opened.vault
    incoming = revisions(initial.opened.vault, current)[kind]
    opened = replace(local.opened, vault=incoming)
    plan = plan_restore(codec.seal(opened), PASSWORD, None if kind == "new" else local)
    assert plan.relation is expected
    assert plan.can_apply() is restorable
    if kind == "new":
        store = Store(store.path.with_name("restored.hexage"))
    before = store.read()
    if restorable:
        assert plan.apply(store).opened.vault == incoming
        backups = list(store.path.parent.glob("backup-*.hexage"))
        assert [p.read_bytes() for p in backups] == ([] if before is None else [before])
    else:
        with pytest.raises(HexageError):
            plan.apply(store)
        assert store.read() == before


def revisions(initial, current):
    child = replace(current.advance(()), changed="2099-01-01T00:00:00.000000+00:00")
    return {
        "new": current,
        "same": current,
        "mutated": replace(current, notes=()),
        "old": initial,
        "newer": child,
        "branch": initial.advance(()),
        "clock": replace(child, changed=current.changed),
        "other": replace(child, vault=identifier()),
    }


def test_stale_restore(active):
    store, session = active
    candidate = replace(session.opened, vault=session.opened.vault.advance((NOTE,)))
    plan = plan_restore(codec.seal(candidate), PASSWORD, session)
    committed = save(store, session, ())
    with pytest.raises(HexageError, match="изменился"):
        plan.apply(store)
    assert unlock(store, PASSWORD).digest == committed.digest


def test_v1_fixture():
    fixture = Path(__file__).with_name("fixtures") / "format-v1.hexage"
    decoded = codec.open_vault(fixture.read_bytes(), PASSWORD)
    assert decoded.vault.notes == (NOTE,)
    rewritten = codec.seal(decoded)
    assert rewritten != fixture.read_bytes()
    assert codec.open_vault(rewritten, PASSWORD).vault == decoded.vault
