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
from threading import Event

import pytest

from hexage import http
from hexage.cloud import Disk, Snapshot
from hexage.model import HexageError


class Answer:
    def __init__(self, status: int, body: bytes = b"", location: str = "") -> None:
        self.status_code = status
        self.body = body
        self.headers = {"Location": location} if location else {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def iter_content(self, chunk_size: int = 65536):
        for start in range(0, len(self.body), chunk_size):
            yield self.body[start : start + chunk_size]


def test_follows_allowed_redirect_without_forwarding_options(monkeypatch):
    calls = []
    answers = [
        Answer(302, location="https://storage.yandex.net/object"),
        Answer(200, body=b"synthetic ciphertext"),
    ]

    def send(method, url, **options):
        calls.append((method, url, options))
        return answers.pop(0)

    monkeypatch.setattr(http.requests, "request", send)
    result = http.request(
        "GET",
        "https://downloader.disk.yandex.ru/file?uid=1",
        Event(),
        binary=True,
        follow=(".yandex.net", ".yandex.ru"),
        headers={"Authorization": "OAuth synthetic"},
        params={"uid": "1"},
    )
    assert result == b"synthetic ciphertext"
    assert calls[1][1] == "https://storage.yandex.net/object"
    assert "headers" not in calls[1][2]
    assert "params" not in calls[1][2]


def test_redirect_without_follow_is_http_error(monkeypatch):
    answer = Answer(302, location="https://storage.yandex.net/object")
    monkeypatch.setattr(http.requests, "request", lambda *_args, **_kwargs: answer)
    with pytest.raises(http.HttpError) as caught:
        http.request("GET", "https://downloader.disk.yandex.ru/file", Event())
    assert caught.value.status == 302


def test_redirect_to_foreign_host_is_rejected(monkeypatch):
    calls = []

    def send(method, url, **options):
        calls.append(url)
        return Answer(302, location="https://evil.example/object")

    monkeypatch.setattr(http.requests, "request", send)
    with pytest.raises(HexageError) as caught:
        http.request(
            "GET",
            "https://downloader.disk.yandex.ru/file",
            Event(),
            follow=(".yandex.ru",),
        )
    assert "перенаправления" in str(caught.value)
    assert calls == ["https://downloader.disk.yandex.ru/file"]


def test_redirects_are_limited(monkeypatch):
    calls = []

    def send(method, url, **options):
        calls.append(url)
        return Answer(302, location="/next")

    monkeypatch.setattr(http.requests, "request", send)
    with pytest.raises(HexageError) as caught:
        http.request(
            "GET",
            "https://storage.yandex.net/start",
            Event(),
            follow=(".yandex.net",),
        )
    assert "слишком много раз" in str(caught.value)
    assert len(calls) == http.MAX_REDIRECTS + 1


def test_disk_download_follows_storage_redirect(monkeypatch):
    name = "d" * 32 + ".hexage"
    link = "https://downloader.disk.yandex.ru/disk/object"
    answers = [
        Answer(200, body=json.dumps({"href": link}).encode()),
        Answer(302, location="https://storage.yandex.net/object"),
        Answer(200, body=b"synthetic ciphertext"),
    ]
    calls = []

    def send(method, url, **options):
        calls.append((method, url, options))
        return answers.pop(0)

    monkeypatch.setattr(http.requests, "request", send)
    snapshot = Snapshot(name, name, "")
    blob = Disk({"Authorization": "OAuth synthetic"}, Event()).download(snapshot)
    assert blob == b"synthetic ciphertext"
    assert calls[0][2]["headers"] == {"Authorization": "OAuth synthetic"}
    assert calls[1][1] == link
    assert calls[2][1] == "https://storage.yandex.net/object"
    assert "headers" not in calls[1][2]
    assert "headers" not in calls[2][2]


def test_post_redirect_is_not_followed(monkeypatch):
    calls = []

    def send(method, url, **options):
        calls.append(url)
        return Answer(302, location="https://storage.yandex.net/object")

    monkeypatch.setattr(http.requests, "request", send)
    with pytest.raises(http.HttpError) as caught:
        http.request(
            "POST",
            "https://oauth.yandex.ru/token",
            Event(),
            data={"grant_type": "authorization_code"},
            follow=(".yandex.ru",),
        )
    assert caught.value.status == 302
    assert len(calls) == 1
