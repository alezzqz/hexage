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
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Event
from typing import Protocol
from urllib.parse import quote

from .http import HttpError, allowed_url, request
from .model import HexageError, identifier
from .oauth import Credentials, Provider, check_cancel

GOOGLE = "https://www.googleapis.com/drive/v3/files"
GOOGLE_HOSTS = (".googleapis.com", ".googleusercontent.com")
YANDEX = "https://cloud-api.yandex.net/v1/disk/resources"
YANDEX_OPERATIONS = "https://cloud-api.yandex.net/v1/disk/operations"
YANDEX_HOSTS = (".yandex.net", ".yandex.ru", ".yandex.com")
EXPORT_OK = "Снимок записан."


@dataclass(frozen=True)
class Snapshot:
    id: str
    name: str
    date: str

    def label(self) -> str:
        try:
            created = datetime.fromisoformat(self.date)
            if created.tzinfo is None:
                raise ValueError
            date = created.astimezone(UTC).strftime("%d.%m.%Y %H:%M:%S UTC")
        except (TypeError, ValueError, OverflowError):
            date = "дата неизвестна"
        return f"{date}  ·  {self.name}"


class Adapter(Protocol):
    def upload(self, name: str, blob: bytes) -> None: ...
    def download(self, snapshot: Snapshot) -> bytes: ...
    def list(self) -> list[Snapshot]: ...
    def delete(self, snapshot: Snapshot) -> None: ...


def valid_name(name: str) -> bool:
    return bool(re.fullmatch("[0-9a-f]{32}\\.hexage", name))


@dataclass(frozen=True, repr=False)
class Drive:
    headers: dict[str, str]
    cancel: Event

    def upload(self, name: str, blob: bytes) -> None:
        boundary = identifier()
        metadata = json.dumps({"name": name, "parents": ["appDataFolder"]}).encode()
        start = f"--{boundary}\r\n".encode()
        body = (
            start
            + b"Content-Type: application/json; charset=UTF-8\r\n\r\n"
            + metadata
            + b"\r\n"
            + start
            + b"Content-Type: application/octet-stream\r\n\r\n"
            + blob
            + f"\r\n--{boundary}--\r\n".encode()
        )
        request(
            "POST",
            "https://www.googleapis.com/upload/drive/v3/files",
            self.cancel,
            params={"uploadType": "multipart", "fields": "id"},
            headers={
                **self.headers,
                "Content-Type": f"multipart/related; boundary={boundary}",
            },
            data=body,
            limit=65536,
        )

    def download(self, snapshot: Snapshot) -> bytes:
        return request(
            "GET",
            f"{GOOGLE}/{quote(snapshot.id, safe='')}",
            self.cancel,
            params={"alt": "media"},
            headers=self.headers,
            binary=True,
            follow=GOOGLE_HOSTS,
        )

    def delete(self, snapshot: Snapshot) -> None:
        if not valid_name(snapshot.name) or not re.fullmatch(
            r"[\w-]+", snapshot.id, re.ASCII
        ):
            raise HexageError("Недопустимый идентификатор снимка.")
        request(
            "DELETE",
            f"{GOOGLE}/{snapshot.id}",
            self.cancel,
            headers=self.headers,
            limit=65536,
        )

    def list(self) -> list[Snapshot]:
        items = []
        params = {
            "spaces": "appDataFolder",
            "fields": "nextPageToken,files(id,name,createdTime)",
            "q": "trashed = false and mimeType != 'application/vnd.google-apps.folder'",
            "pageSize": 100,
            "orderBy": "createdTime desc",
        }
        for _ in range(100):
            response = request(
                "GET", GOOGLE, self.cancel, params=params, headers=self.headers
            )
            items.extend(
                Snapshot(f["id"], f["name"], f.get("createdTime", ""))
                for f in response.get("files", [])
                if valid_name(f["name"])
            )
            next_page = response.get("nextPageToken")
            if not next_page:
                return items
            params["pageToken"] = next_page
        raise HexageError("Слишком много объектов в папке приложения.")


@dataclass(frozen=True, repr=False)
class Disk:
    headers: dict[str, str]
    cancel: Event

    def transfer_url(self, action: str, name: str) -> str:
        if not valid_name(name):
            raise HexageError("Недопустимое имя снимка.")
        options = {"path": f"app:/{name}"}
        if action == "upload":
            options["overwrite"] = "false"
        result = request(
            "GET",
            f"{YANDEX}/{action}",
            self.cancel,
            params=options,
            headers=self.headers,
            limit=65536,
        )
        href = result["href"]
        if not allowed_url(href, YANDEX_HOSTS):
            raise HexageError("Недопустимый адрес передачи снимка.")
        return href

    def upload(self, name: str, blob: bytes) -> None:
        request(
            "PUT",
            self.transfer_url("upload", name),
            self.cancel,
            data=blob,
            binary=True,
            limit=65536,
        )

    def download(self, snapshot: Snapshot) -> bytes:
        return request(
            "GET",
            self.transfer_url("download", snapshot.id),
            self.cancel,
            binary=True,
            follow=YANDEX_HOSTS,
        )

    def delete(self, snapshot: Snapshot) -> None:
        if snapshot.id != snapshot.name or not valid_name(snapshot.name):
            raise HexageError("Недопустимое имя снимка.")
        result = request(
            "DELETE",
            YANDEX,
            self.cancel,
            params={"path": f"app:/{snapshot.name}", "permanently": "true"},
            headers=self.headers,
            limit=65536,
        )
        if result:
            self.wait_for_delete(result.get("href"))

    def wait_for_delete(self, href: str | None) -> None:
        # Never send the OAuth token to an arbitrary URL from a response body.
        if not isinstance(href, str) or not re.fullmatch(
            rf"{re.escape(YANDEX_OPERATIONS)}/[A-Za-z0-9_-]+", href
        ):
            raise HexageError("Не удалось подтвердить удаление снимка.")
        for _ in range(30):
            result = request(
                "GET", href, self.cancel, headers=self.headers, limit=65536
            )
            status = result.get("status")
            if status == "success":
                return
            if status == "failed":
                raise HexageError("Яндекс Диск не удалил снимок.")
            if status != "in-progress" or self.cancel.wait(1):
                break
        raise HexageError("Не удалось подтвердить удаление. Проверьте список снимков.")

    def list(self) -> list[Snapshot]:
        items = []
        for offset in range(0, 10000, 100):
            result = request(
                "GET",
                YANDEX,
                self.cancel,
                headers=self.headers,
                params={
                    "path": "app:/",
                    "limit": 100,
                    "offset": offset,
                    "sort": "-created",
                },
            )
            page = result["_embedded"]["items"]
            items.extend(
                Snapshot(f["name"], f["name"], f.get("created", ""))
                for f in page
                if f["type"] == "file" and valid_name(f["name"])
            )
            if len(page) < 100 or offset + len(page) >= result["_embedded"].get(
                "total", 10001
            ):
                return items
        raise HexageError("Слишком много объектов в папке приложения.")


@dataclass(frozen=True)
class Cloud:
    provider: Provider
    credentials: Credentials

    def call(self, action, cancel: Event):
        check_cancel(cancel)
        token = self.credentials.access(self.provider, cancel)
        if self.provider.name == "Google Drive":
            adapter = Drive({"Authorization": f"Bearer {token}"}, cancel)
        else:
            adapter = Disk({"Authorization": f"OAuth {token}"}, cancel)
        try:
            return action(adapter)
        except HttpError as error:
            if error.status == 401:
                self.credentials.disconnect(self.provider)
                raise HexageError(
                    "Авторизация истекла. Повторите операцию для входа."
                ) from None
            raise


def export_to(clouds: tuple[Cloud, ...], blob: bytes, cancel: Event) -> dict[str, str]:
    name = f"{identifier()}.hexage"
    results = {}
    for cloud in clouds:
        try:
            cloud.call(lambda adapter: adapter.upload(name, blob), cancel)
        except HexageError as error:
            results[cloud.provider.name] = str(error)
        except Exception:
            results[cloud.provider.name] = "Не удалось подтвердить запись снимка."
        else:
            results[cloud.provider.name] = EXPORT_OK
    return results
