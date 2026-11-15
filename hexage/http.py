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
from time import monotonic
from urllib.parse import urljoin, urlsplit

import requests

from .codec import MAX_FILE
from .model import HexageError

REDIRECTS = frozenset({301, 302, 303, 307, 308})
MAX_REDIRECTS = 5


class HttpError(HexageError):
    def __init__(self, status: int) -> None:
        super().__init__(f"Сервис вернул HTTP {status}.")
        self.status = status


def valid_url(url: str) -> bool:
    parsed = urlsplit(url)
    return (
        parsed.scheme == "https" and bool(parsed.hostname) and parsed.username is None
    )


def allowed_url(url: str, suffixes: tuple[str, ...]) -> bool:
    host = urlsplit(url).hostname or ""
    return valid_url(url) and any(host.endswith(suffix) for suffix in suffixes)


def redirect_url(current: str, location: str, follow: tuple[str, ...]) -> str:
    target = urljoin(current, location)
    if not location or not allowed_url(target, follow):
        raise HexageError("Недопустимый адрес перенаправления.")
    return target


def request(
    method: str,
    url: str,
    cancel: Event,
    *,
    limit: int = MAX_FILE,
    binary: bool = False,
    follow: tuple[str, ...] = (),
    **options,
):
    if not valid_url(url):
        raise HexageError("Недопустимый адрес облачного сервиса.")
    try:
        data = fetch(method, url, cancel, limit, follow, options)
        if binary:
            return bytes(data)
        result = json.loads(data) if data else {}
        if not isinstance(result, dict):
            raise ValueError
        return result
    except (requests.RequestException, ValueError, RecursionError):
        raise HexageError(
            "Нет связи с облачным сервисом или ответ недопустим."
        ) from None


def fetch(
    method: str,
    url: str,
    cancel: Event,
    limit: int,
    follow: tuple[str, ...],
    options: dict,
) -> bytearray:
    for hop in range(MAX_REDIRECTS + 1):
        if cancel.is_set():
            raise HexageError("Операция отменена.")
        with requests.request(
            method,
            url,
            timeout=(8, 12),
            stream=True,
            allow_redirects=False,
            **options,
        ) as response:
            location = response.headers.get("Location", "")
            if (
                follow
                and method in {"GET", "HEAD"}
                and response.status_code in REDIRECTS
            ):
                if hop == MAX_REDIRECTS:
                    raise HexageError("Сервис перенаправляет слишком много раз.")
                url = redirect_url(url, location, follow)
                options = {}
                continue
            if not 200 <= response.status_code < 300:
                raise HttpError(response.status_code)
            return read_response(response, cancel, limit)
    raise HexageError("Сервис перенаправляет слишком много раз.")


def read_response(response: requests.Response, cancel: Event, limit: int) -> bytearray:
    deadline = monotonic() + 60
    data = bytearray()
    for chunk in response.iter_content(chunk_size=65536):
        if cancel.is_set() or monotonic() > deadline:
            raise HexageError("Передача отменена или истекло время ожидания.")
        data.extend(chunk)
        if len(data) > limit:
            raise HexageError("Ответ сервиса слишком большой.")
    return data
