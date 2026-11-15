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

from contextlib import nullcontext
from threading import Event
from types import SimpleNamespace

import pytest
import requests

from hexage import cloud, http
from hexage.cloud import Disk, Drive, Snapshot, export_to
from hexage.model import HexageError


def test_partial_success(monkeypatch):
    writes = []

    def offline(*_args, **_kwargs):
        raise requests.ConnectionError("synthetic offline")

    monkeypatch.setattr(http.requests, "request", offline)
    good = SimpleNamespace(upload=lambda name, blob: writes.append((name, blob)))

    def fail(_name: str, _blob: bytes) -> None:
        http.request("POST", "https://example.com", Event())

    def service(name, adapter):
        return SimpleNamespace(
            provider=SimpleNamespace(name=name),
            call=lambda action, cancel: action(adapter),
        )

    results = export_to(
        (service("offline", SimpleNamespace(upload=fail)), service("working", good)),
        b"synthetic ciphertext",
        Event(),
    )
    assert "Нет связи" in results["offline"]
    assert results["working"] == "Снимок записан."
    assert writes[0][0].endswith(".hexage")
    assert writes[0][1] == b"synthetic ciphertext"


def test_cancel_prevents_network(monkeypatch):
    cancel = Event()
    cancel.set()

    def unexpected(*_args, **_kwargs):
        raise AssertionError("Cancelled operation contacted HTTP")

    monkeypatch.setattr(http.requests, "request", unexpected)
    try:
        http.request("GET", "https://example.com", cancel)
    except HexageError as error:
        assert "отменена" in str(error)
    else:
        raise AssertionError("Cancelled operation succeeded")


def test_drive_uses_app_data_and_creates_new_object(monkeypatch):
    name = "a" * 32 + ".hexage"
    captured = []

    def send(method, url, cancel, **options):
        captured.append((method, url, options))
        return {"files": [{"id": "snapshot", "name": name}]} if method == "GET" else {}

    monkeypatch.setattr(cloud, "request", send)
    drive = Drive({}, Event())
    assert drive.list() == [Snapshot("snapshot", name, "")]
    drive.upload(name, b"synthetic ciphertext")
    assert captured[0][2]["params"]["spaces"] == "appDataFolder"
    assert captured[1][0] == "POST"
    assert b'"parents": ["appDataFolder"]' in captured[1][2]["data"]


def test_disk_presigns_transfers_without_overwrite_or_token_forwarding(monkeypatch):
    name = "b" * 32 + ".hexage"
    captured = []

    def send(method, url, cancel, **options):
        captured.append((method, url, options))
        if url.startswith(cloud.YANDEX):
            return {"href": "https://transfer.yandex.net/object"}
        return b"synthetic ciphertext"

    monkeypatch.setattr(cloud, "request", send)
    disk = Disk({"Authorization": "OAuth synthetic"}, Event())
    disk.upload(name, b"synthetic ciphertext")
    assert disk.download(Snapshot(name, name, "")) == b"synthetic ciphertext"
    assert captured[0][2]["params"] == {"path": f"app:/{name}", "overwrite": "false"}
    assert captured[1][0] == "PUT"
    assert "headers" not in captured[1][2]
    assert "headers" not in captured[3][2]
    assert captured[3][2]["follow"] == cloud.YANDEX_HOSTS


def test_drive_download_allows_media_redirect(monkeypatch):
    name = "c" * 32 + ".hexage"
    captured = []

    def send(method, url, cancel, **options):
        captured.append(options)
        return b"synthetic ciphertext"

    monkeypatch.setattr(cloud, "request", send)
    drive = Drive({}, Event())
    assert drive.download(Snapshot("snapshot", name, "")) == b"synthetic ciphertext"
    assert captured[0]["follow"] == cloud.GOOGLE_HOSTS


def test_snapshot_date_normalizes_provider_offset_and_handles_missing_date():
    name = "a" * 32 + ".hexage"
    assert Snapshot("id", name, "2026-01-01T01:30:00+03:00").label() == (
        f"31.12.2025 22:30:00 UTC  ·  {name}"
    )
    assert Snapshot("id", name, "").label() == f"дата неизвестна  ·  {name}"


def test_drive_deletes_only_the_selected_file(monkeypatch):
    name = "a" * 32 + ".hexage"
    calls = []
    monkeypatch.setattr(cloud, "request", lambda *args, **_: calls.append(args))
    cancel = Event()
    adapter = Drive({}, cancel)
    adapter.delete(Snapshot("chosen_id", name, ""))
    with pytest.raises(HexageError):
        adapter.delete(Snapshot("..", name, ""))
    assert calls == [("DELETE", f"{cloud.GOOGLE}/chosen_id", cancel)]


@pytest.mark.parametrize("status", ["success", "failed"])
def test_disk_checks_async_delete_result(monkeypatch, status):
    name = "b" * 32 + ".hexage"
    operation = f"{cloud.YANDEX_OPERATIONS}/operation-id"
    calls = []

    def send(method, url, _cancel, **options):
        calls.append((method, url, options.get("params")))
        return {"href": operation} if method == "DELETE" else {"status": status}

    monkeypatch.setattr(cloud, "request", send)
    adapter = Disk({}, Event())
    with pytest.raises(HexageError) if status == "failed" else nullcontext():
        adapter.delete(Snapshot(name, name, ""))
    assert calls == [
        ("DELETE", cloud.YANDEX, {"path": f"app:/{name}", "permanently": "true"}),
        ("GET", operation, None),
    ]


def test_disk_rejects_unsafe_delete_paths_and_operation_links(monkeypatch):
    name = "b" * 32 + ".hexage"
    calls = []

    def send(method, *_args, **_options):
        calls.append(method)
        return {"href": "https://example.com/operation-id"}

    monkeypatch.setattr(cloud, "request", send)
    adapter = Disk({}, Event())
    with pytest.raises(HexageError):
        adapter.delete(Snapshot("app:/", name, ""))
    with pytest.raises(HexageError):
        adapter.delete(Snapshot(name, name, ""))
    assert calls == ["DELETE"]
